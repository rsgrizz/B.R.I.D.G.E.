# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.5
# Date: 5/20/2026
# Purpose: Automated unit tests covering format detection, BFS path planning, and framework stability.

import io
import hashlib
import unittest
import tempfile
import os
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

from app.core.models import (
    FileFormat,
    PathRisk,
    PlanConfidence,
    DetectionMethod,
    DetectionResult,
    PlannerError,
    ConversionEdge,
    ValidationSeverity,
    ValidationCode,
    ValidationResult,
    DryRunResult,
    EstimatedSpaceRequirement,
)
from app.core.detector import FormatDetector
from app.core.conversion_planner import ConversionPlanner
from app.core.conversion_registry import ConversionRegistry
from app.core.tool_runner import ToolRunner
from app.core.hash_service import HashService
from app.core.preflight_validator import PreflightValidator
from app.utils.paths import AppPaths

class TestScaffoldWiring(unittest.TestCase):
    """Smoke test suite confirming clean module imports, model states,
    and path resolver alignments.
    """

    def test_core_imports(self):
        """Verifies that all core services can be imported without circular dependencies."""
        self.assertIsNotNone(FileFormat)
        self.assertIsNotNone(PathRisk)
        self.assertIsNotNone(FormatDetector)
        self.assertIsNotNone(ConversionPlanner)
        self.assertIsNotNone(ConversionRegistry)
        self.assertIsNotNone(AppPaths)

    def test_paths_resolver(self):
        """Validates that Path Resolution resolves to the expected local folders."""
        app_root = AppPaths.get_app_root()
        self.assertTrue(isinstance(app_root, Path))
        self.assertTrue(app_root.exists())
        
        tools_dir = AppPaths.get_tools_dir()
        self.assertTrue(tools_dir.exists())
        
        logs_dir = AppPaths.get_logs_dir()
        self.assertTrue(logs_dir.exists())

    def test_registry_populated(self):
        """Verifies that the Conversion Registry initializes with standard conversion edges."""
        edges = ConversionRegistry.get_supported_edges()
        self.assertTrue(len(edges) > 0)
        
        # Verify RAW ➔ VMDK exists
        raw_to_vmdk = [e for e in edges if e.source == FileFormat.RAW and e.target == FileFormat.VMDK]
        self.assertEqual(len(raw_to_vmdk), 1)

    def test_planner_direct_path(self):
        """Confirms that direct conversion paths (e.g. RAW ➔ VMDK) are resolved in a single step."""
        plan = ConversionPlanner.plan_conversion(FileFormat.RAW, FileFormat.VMDK)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.total_steps, 1)
        self.assertEqual(plan.has_experimental, False)
        
        step = plan.steps[0]
        self.assertEqual(step.source_format, FileFormat.RAW)
        self.assertEqual(step.target_format, FileFormat.VMDK)
        self.assertEqual(step.is_intermediate, False)

    def test_planner_multistep_path(self):
        """Confirms that multi-step conversion paths (e.g. E01 ➔ VHD) resolve using intermediates."""
        plan = ConversionPlanner.plan_conversion(FileFormat.E01, FileFormat.VHD)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.total_steps, 2)
        self.assertEqual(plan.has_experimental, False)
        
        step_1 = plan.steps[0]
        step_2 = plan.steps[1]
        
        self.assertEqual(step_1.source_format, FileFormat.E01)
        self.assertEqual(step_1.target_format, FileFormat.RAW)
        self.assertEqual(step_1.is_intermediate, True)
        
        self.assertEqual(step_2.source_format, FileFormat.RAW)
        self.assertEqual(step_2.target_format, FileFormat.VHD)
        self.assertEqual(step_2.is_intermediate, False)

    def test_planner_unsupported_conversion(self):
        """Confirms that unsupported paths or UNKNOWN formats raise PlannerError."""
        # RAW to E01 is not registered and not supported
        with self.assertRaises(PlannerError) as ctx:
            ConversionPlanner.plan_conversion(FileFormat.RAW, FileFormat.E01)
        self.assertIn("Unsupported conversion path", str(ctx.exception))
        
        # UNKNOWN format conversions
        with self.assertRaises(PlannerError):
            ConversionPlanner.plan_conversion(FileFormat.UNKNOWN, FileFormat.VMDK)
            
        with self.assertRaises(PlannerError):
            ConversionPlanner.plan_conversion(FileFormat.RAW, FileFormat.UNKNOWN)
            
        # Identical source and target formats
        with self.assertRaises(PlannerError):
            ConversionPlanner.plan_conversion(FileFormat.RAW, FileFormat.RAW)

    def test_planner_experimental_propagation(self):
        """Validates that experimental edge risk properties propagate successfully to the plan."""
        # EX01 -> RAW is registered as experimental
        plan = ConversionPlanner.plan_conversion(FileFormat.EX01, FileFormat.RAW)
        self.assertIsNotNone(plan)
        self.assertTrue(plan.has_experimental)
        self.assertEqual(plan.confidence, PlanConfidence.EXPERIMENTAL)
        
        step = plan.steps[0]
        self.assertTrue(step.experimental)
        self.assertEqual(step.risk, PathRisk.EXPERIMENTAL)

        # Multi-step with an experimental start: EX01 -> RAW -> VMDK
        plan_multi = ConversionPlanner.plan_conversion(FileFormat.EX01, FileFormat.VMDK)
        self.assertIsNotNone(plan_multi)
        self.assertTrue(plan_multi.has_experimental)
        self.assertEqual(plan_multi.confidence, PlanConfidence.EXPERIMENTAL)
        self.assertEqual(plan_multi.total_steps, 2)
        
        # DMG -> RAW -> QCOW2 is experimental
        plan_dmg = ConversionPlanner.plan_conversion(FileFormat.DMG, FileFormat.QCOW2)
        self.assertIsNotNone(plan_dmg)
        self.assertTrue(plan_dmg.has_experimental)

    def test_planner_preference_for_non_experimental(self):
        """Confirms that Dijkstra solver prefers lower weight/stable paths over experimental ones."""
        # We will inject a custom direct but experimental edge from E01 to VMDK
        original_edges = ConversionRegistry._edges
        
        # Direct experimental edge E01 -> VMDK with high weight
        exp_edge = ConversionEdge(
            source=FileFormat.E01,
            target=FileFormat.VMDK,
            backend_tool="mock-tool",
            command_template_tokens=["mock", "--direct", "{input}", "{output}"],
            experimental=True,
            notes="Experimental direct path",
            weight=15.0
        )
        
        try:
            # Registry now has the original edges + the new direct experimental edge
            ConversionRegistry._edges = original_edges + [exp_edge]
            
            # Plan conversion E01 -> VMDK
            # Should prefer E01 -> RAW (stable, weight 1) -> VMDK (stable, weight 1) total weight ~2
            # instead of direct E01 -> VMDK (experimental, weight 15)
            plan = ConversionPlanner.plan_conversion(FileFormat.E01, FileFormat.VMDK)
            
            self.assertIsNotNone(plan)
            self.assertEqual(plan.total_steps, 2)
            self.assertFalse(plan.has_experimental)
            self.assertEqual(plan.steps[0].source_format, FileFormat.E01)
            self.assertEqual(plan.steps[0].target_format, FileFormat.RAW)
            self.assertEqual(plan.steps[1].source_format, FileFormat.RAW)
            self.assertEqual(plan.steps[1].target_format, FileFormat.VMDK)
            
            # Now let's test if we set the direct edge to stable with low weight (e.g. weight=0.5)
            stable_direct_edge = ConversionEdge(
                source=FileFormat.E01,
                target=FileFormat.VMDK,
                backend_tool="mock-tool",
                command_template_tokens=["mock", "--direct", "{input}", "{output}"],
                experimental=False,
                notes="Stable direct path",
                weight=0.5
            )
            ConversionRegistry._edges = original_edges + [stable_direct_edge]
            
            plan_direct = ConversionPlanner.plan_conversion(FileFormat.E01, FileFormat.VMDK)
            self.assertIsNotNone(plan_direct)
            self.assertEqual(plan_direct.total_steps, 1)
            self.assertEqual(plan_direct.steps[0].backend_tool, "mock-tool")
            
        finally:
            ConversionRegistry._edges = original_edges

    def test_planner_output_structure_integrity(self):
        """Verifies that all structured data attributes are cleanly generated inside the ConversionPlan."""
        plan = ConversionPlanner.plan_conversion(FileFormat.E01, FileFormat.VMDK, "/input/path.e01", "/output/path.vmdk")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.total_steps, 2)
        
        # Step 1 details
        s1 = plan.steps[0]
        self.assertEqual(s1.step_num, 1)
        self.assertEqual(s1.source_format, FileFormat.E01)
        self.assertEqual(s1.target_format, FileFormat.RAW)
        self.assertEqual(s1.input_file, "/input/path.e01")
        # Intermediate temp file should be co-located with target path
        self.assertEqual(s1.output_file, "/output/path_temp_step1.raw")
        self.assertEqual(s1.backend_tool, "ewfexport")
        self.assertEqual(s1.command_template_tokens, ["ewfexport", "-t", "{output_no_ext}", "-f", "raw", "{input}"])
        self.assertEqual(s1.command_args, ["ewfexport", "-t", "/output/path_temp_step1", "-f", "raw", "/input/path.e01"])
        self.assertTrue(s1.is_intermediate)
        self.assertFalse(s1.experimental)
        self.assertEqual(s1.risk, PathRisk.STABLE)
        
        # Step 2 details
        s2 = plan.steps[1]
        self.assertEqual(s2.step_num, 2)
        self.assertEqual(s2.source_format, FileFormat.RAW)
        self.assertEqual(s2.target_format, FileFormat.VMDK)
        self.assertEqual(s2.input_file, "/output/path_temp_step1.raw")
        self.assertEqual(s2.output_file, "/output/path.vmdk")
        self.assertEqual(s2.backend_tool, "qemu-img")
        self.assertEqual(s2.command_template_tokens, ["qemu-img", "convert", "-f", "raw", "-O", "vmdk", "{input}", "{output}"])
        self.assertEqual(s2.command_args, ["qemu-img", "convert", "-f", "raw", "-O", "vmdk", "/output/path_temp_step1.raw", "/output/path.vmdk"])
        self.assertFalse(s2.is_intermediate)
        self.assertFalse(s2.experimental)
        self.assertEqual(s2.risk, PathRisk.STABLE)


class TestFormatDetector(unittest.TestCase):
    """Rigorous unit test suite validating binary signature checks and extension fallbacks."""

    def setUp(self):
        self.temp_files = []

    def tearDown(self):
        # Remove any temporary test files created
        for filepath in self.temp_files:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass

    def _create_temp_file(self, content: bytes, suffix: str = ".tmp") -> str:
        """Creates a temporary binary file with custom content."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        with open(path, "wb") as f:
            f.write(content)
        self.temp_files.append(path)
        return path

    def test_e01_signature(self):
        """Checks E01 EVF magic header signature identification."""
        content = b"EVF\x09\x0d\x0a\xff\x00" + b"\x00" * 504
        path = self._create_temp_file(content, ".e01")
        result = FormatDetector.detect_format(path)
        
        self.assertEqual(result.format, FileFormat.E01)
        self.assertEqual(result.method, DetectionMethod.SIGNATURE)
        self.assertEqual(result.confidence, "High")

    def test_ex01_signature(self):
        """Checks Ex01 EVF2 magic header signature identification."""
        content = b"EVF2\x0d\x0a\xff\x00" + b"\x00" * 504
        path = self._create_temp_file(content, ".ex01")
        result = FormatDetector.detect_format(path)
        
        self.assertEqual(result.format, FileFormat.EX01)
        self.assertEqual(result.method, DetectionMethod.SIGNATURE)
        self.assertEqual(result.confidence, "High")

    def test_qcow2_signature(self):
        """Checks QCOW2 magic header signature identification."""
        content = b"QFI\xfb" + b"\x00" * 508
        path = self._create_temp_file(content, ".qcow2")
        result = FormatDetector.detect_format(path)
        
        self.assertEqual(result.format, FileFormat.QCOW2)
        self.assertEqual(result.method, DetectionMethod.SIGNATURE)
        self.assertEqual(result.confidence, "High")

    def test_vmdk_signature(self):
        """Checks VMDK magic header signature identification."""
        content = b"KDMV" + b"\x00" * 508
        path = self._create_temp_file(content, ".vmdk")
        result = FormatDetector.detect_format(path)
        
        self.assertEqual(result.format, FileFormat.VMDK)
        self.assertEqual(result.method, DetectionMethod.SIGNATURE)
        self.assertEqual(result.confidence, "High")

    def test_vhdx_signature(self):
        """Checks VHDX magic header signature identification."""
        content = b"vhdxfile" + b"\x00" * 504
        path = self._create_temp_file(content, ".vhdx")
        result = FormatDetector.detect_format(path)
        
        self.assertEqual(result.format, FileFormat.VHDX)
        self.assertEqual(result.method, DetectionMethod.SIGNATURE)
        self.assertEqual(result.confidence, "High")

    def test_dmg_trailer_signature(self):
        """Checks Apple DMG trailer 'koly' signature detection."""
        # Create a file exactly 1024 bytes. Last 512 bytes is the trailer, starting with 'koly'
        content = b"\x00" * 512 + b"koly" + b"\x00" * 508
        path = self._create_temp_file(content, ".dmg")
        result = FormatDetector.detect_format(path)
        
        self.assertEqual(result.format, FileFormat.DMG)
        self.assertEqual(result.method, DetectionMethod.SIGNATURE)
        self.assertEqual(result.confidence, "High")

    def test_vhd_trailer_signature(self):
        """Checks legacy VHD trailer 'conectix' signature detection."""
        content = b"\x00" * 512 + b"conectix" + b"\x00" * 504
        path = self._create_temp_file(content, ".vhd")
        result = FormatDetector.detect_format(path)
        
        self.assertEqual(result.format, FileFormat.VHD)
        self.assertEqual(result.method, DetectionMethod.SIGNATURE)
        self.assertEqual(result.confidence, "High")

    def test_extension_fallback(self):
        """Checks that files with standard suffixes but no valid magic signature map via extension."""
        # A file with raw zeros, but suffix .vmdk should map to VMDK with Medium confidence (Extension fallback)
        content = b"\x00" * 1024
        path = self._create_temp_file(content, ".vmdk")
        result = FormatDetector.detect_format(path)
        
        self.assertEqual(result.format, FileFormat.VMDK)
        self.assertEqual(result.method, DetectionMethod.EXTENSION)
        self.assertEqual(result.confidence, "Medium")

    def test_raw_extension_mapping(self):
        """RAW/DD images have no magic bytes, so they must always classify via extension fallback."""
        content = b"\x00" * 1024
        path = self._create_temp_file(content, ".raw")
        result = FormatDetector.detect_format(path)
        
        self.assertEqual(result.format, FileFormat.RAW)
        self.assertEqual(result.method, DetectionMethod.EXTENSION)
        self.assertEqual(result.confidence, "Medium")

    def test_unknown_format(self):
        """An unknown extension with no valid magic signature evaluates to UNKNOWN."""
        content = b"\x00" * 1024
        path = self._create_temp_file(content, ".xyz")
        result = FormatDetector.detect_format(path)
        
        self.assertEqual(result.format, FileFormat.UNKNOWN)
        self.assertEqual(result.method, DetectionMethod.UNKNOWN)
        self.assertEqual(result.confidence, "Low")

    def test_l01_signature(self):
        """Checks L01 Logical Evidence File signature identification."""
        content = b"LVF\x09\x0d\x0a\xff\x00" + b"\x00" * 504
        path = self._create_temp_file(content, ".l01")
        result = FormatDetector.detect_format(path)
        
        self.assertEqual(result.format, FileFormat.EX01)
        self.assertEqual(result.method, DetectionMethod.SIGNATURE)
        self.assertEqual(result.confidence, "High")

    def test_ewf_split_segment_fallbacks(self):
        """Checks pattern-based E01/EWF family extension detection for various segment names."""
        test_cases = [
            (".e02", FileFormat.E01),
            (".e99", FileFormat.E01),
            (".eaa", FileFormat.E01),
            (".ezz", FileFormat.E01),
            (".s01", FileFormat.E01),
            (".s05", FileFormat.E01),
            (".saa", FileFormat.E01),
            (".ex02", FileFormat.EX01),
            (".exzz", FileFormat.EX01),
            (".l02", FileFormat.EX01),
            (".laa", FileFormat.EX01),
        ]
        
        for suffix, expected_fmt in test_cases:
            content = b"\x00" * 512
            path = self._create_temp_file(content, suffix)
            result = FormatDetector.detect_format(path)
            
            self.assertEqual(result.format, expected_fmt, f"Failed on suffix: {suffix}")
            self.assertEqual(result.method, DetectionMethod.EXTENSION)
            self.assertEqual(result.confidence, "Medium")


class TestToolRunner(unittest.TestCase):
    """Unit tests validating external command invocation, path resolution, 
    and cancellation dynamics inside ToolRunner.
    """

    def setUp(self):
        self.cancel_event = Event()
        self.logs = []
        self.log_callback = lambda line: self.logs.append(line)

    @patch("subprocess.Popen")
    def test_run_command_success(self, mock_popen):
        """Validates that a successful subprocess run captures stdout, exit code, and returns success."""
        # Mock process instance
        mock_proc = MagicMock()
        # StringIO streams drain almost instantly; poll() will be called once the queue
        # empties and process.poll() is not None. Use a stable return_value.
        mock_proc.poll.return_value = 0
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0
        mock_proc.stdout = io.StringIO("Progress: 50%\nProgress: 100%\n")
        mock_proc.stderr = io.StringIO("")
        mock_popen.return_value = mock_proc

        cmd = ["qemu-img", "convert", "in.raw", "out.vmdk"]
        result = ToolRunner.run_command(cmd, self.log_callback, self.cancel_event)

        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.cancelled)
        self.assertIn("Progress: 50%", self.logs)
        self.assertIn("Progress: 100%", self.logs)

    @patch("subprocess.Popen")
    def test_run_command_non_zero_exit(self, mock_popen):
        """Verifies that non-zero exit codes propagate as failure results."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1
        mock_proc.returncode = 1
        mock_proc.wait.return_value = 1
        mock_proc.stdout = io.StringIO("Error: Invalid header\n")
        mock_proc.stderr = io.StringIO("Detailed error description")
        mock_popen.return_value = mock_proc

        cmd = ["qemu-img", "convert", "bad.raw", "out.vmdk"]
        result = ToolRunner.run_command(cmd, self.log_callback, self.cancel_event)

        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error: Invalid header", self.logs)
        self.assertIn("[STDERR]: Detailed error description", self.logs)

    @patch("subprocess.Popen")
    def test_run_command_immediate_cancel(self, mock_popen):
        """Checks that active cancellation events skip invocation altogether."""
        self.cancel_event.set()
        cmd = ["qemu-img", "convert", "in.raw", "out.vmdk"]
        
        result = ToolRunner.run_command(cmd, self.log_callback, self.cancel_event)
        
        mock_popen.assert_not_called()
        self.assertFalse(result.success)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.exit_code, -1)

    @patch("subprocess.Popen")
    def test_run_command_mid_execution_cancel(self, mock_popen):
        """Checks that mid-run cancellation triggers terminate/kill sequence and returns cancelled status."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdout = io.StringIO("Writing sector 1\nWriting sector 2\n")
        mock_proc.stderr = io.StringIO("")
        mock_popen.return_value = mock_proc
        
        def cancellable_cb(line):
            self.logs.append(line)
            if "sector 2" in line:
                self.cancel_event.set()

        cmd = ["qemu-img", "convert", "in.raw", "out.vmdk"]
        result = ToolRunner.run_command(cmd, cancellable_cb, self.cancel_event)

        self.assertFalse(result.success)
        self.assertTrue(result.cancelled)
        mock_proc.terminate.assert_called_once()
        self.assertEqual(result.exit_code, -9)

    @patch("shutil.which")
    @patch("pathlib.Path.is_file")
    @patch("subprocess.Popen")
    def test_tool_path_resolution(self, mock_popen, mock_is_file, mock_which):
        """Validates that ToolRunner resolves tool paths locally in tools/ folder before host PATH."""

        def make_proc():
            proc = MagicMock()
            proc.poll.return_value = 0
            proc.returncode = 0
            proc.wait.return_value = 0
            # Fresh StringIO per call — avoids exhausted-stream false negatives
            proc.stdout = io.StringIO("")
            proc.stderr = io.StringIO("")
            return proc

        mock_popen.side_effect = [make_proc(), make_proc()]

        # 1. Local tools folder hit
        mock_is_file.return_value = True

        cmd = ["qemu-img", "convert"]
        ToolRunner.run_command(cmd, self.log_callback, self.cancel_event)

        args, _ = mock_popen.call_args_list[0]
        called_cmd = args[0]
        self.assertTrue(
            called_cmd[0].endswith("qemu-img") or called_cmd[0].endswith("qemu-img.exe")
        )

        # 2. Local hit missed — fall back to system PATH
        mock_is_file.return_value = False
        mock_which.return_value = "/usr/bin/system-qemu-img"

        self.cancel_event.clear()
        ToolRunner.run_command(cmd, self.log_callback, self.cancel_event)

        args, _ = mock_popen.call_args_list[1]
        called_cmd = args[0]
        self.assertEqual(called_cmd[0], "/usr/bin/system-qemu-img")


class TestHashService(unittest.TestCase):
    """Comprehensive unit tests for HashService: digest correctness, progress callbacks,
    cancellation semantics, edge-case files, and error handling.
    """

    def setUp(self):
        self.cancel_event = Event()
        self.progress_values = []
        self.progress_cb = lambda pct: self.progress_values.append(pct)

    def tearDown(self):
        self.cancel_event.clear()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _make_temp_file(self, content: bytes) -> str:
        """Creates a temporary file with the given content and returns its path."""
        fd, path = tempfile.mkstemp()
        os.close(fd)
        with open(path, "wb") as f:
            f.write(content)
        self.addCleanup(lambda p=path: os.remove(p) if os.path.exists(p) else None)
        return path

    # ------------------------------------------------------------------
    # Digest correctness
    # ------------------------------------------------------------------

    def test_known_digest_small_file(self):
        """Verifies MD5, SHA-1, and SHA-256 match Python's own hashlib for a small payload."""
        content = b"B.R.I.D.G.E. - Phase 9 Hash Test\n"
        path = self._make_temp_file(content)

        expected_md5    = hashlib.md5(content, usedforsecurity=False).hexdigest()
        expected_sha1   = hashlib.sha1(content, usedforsecurity=False).hexdigest()
        expected_sha256 = hashlib.sha256(content).hexdigest()

        result = HashService.calculate_hashes(path, self.progress_cb, self.cancel_event)

        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)
        self.assertEqual(result.md5, expected_md5)
        self.assertEqual(result.sha1, expected_sha1)
        self.assertEqual(result.sha256, expected_sha256)

    def test_known_digest_multi_chunk(self):
        """Verifies digest correctness across multiple 64 KB chunks (2.5 × CHUNK_SIZE)."""
        content = os.urandom(int(HashService.CHUNK_SIZE * 2.5))
        path = self._make_temp_file(content)

        expected_md5    = hashlib.md5(content, usedforsecurity=False).hexdigest()
        expected_sha256 = hashlib.sha256(content).hexdigest()

        result = HashService.calculate_hashes(path, self.progress_cb, self.cancel_event)

        self.assertTrue(result.success)
        self.assertEqual(result.md5, expected_md5)
        self.assertEqual(result.sha256, expected_sha256)

    # ------------------------------------------------------------------
    # Progress callback
    # ------------------------------------------------------------------

    def test_progress_ends_at_100(self):
        """The final progress callback value must always be 100."""
        content = b"progress test payload"
        path = self._make_temp_file(content)

        HashService.calculate_hashes(path, self.progress_cb, self.cancel_event)

        self.assertTrue(len(self.progress_values) >= 1)
        self.assertEqual(self.progress_values[-1], 100)

    def test_progress_monotonically_non_decreasing(self):
        """Progress values must never go backwards across any sequence of callbacks."""
        # Use 3 chunks so we get multiple progress ticks
        content = os.urandom(HashService.CHUNK_SIZE * 3)
        path = self._make_temp_file(content)

        HashService.calculate_hashes(path, self.progress_cb, self.cancel_event)

        for i in range(1, len(self.progress_values)):
            self.assertGreaterEqual(
                self.progress_values[i], self.progress_values[i - 1],
                msg=f"Progress went backwards at index {i}: "
                    f"{self.progress_values[i - 1]} → {self.progress_values[i]}"
            )

    def test_progress_zero_byte_file_still_emits_100(self):
        """A zero-byte file must still emit a final 100% progress tick."""
        path = self._make_temp_file(b"")

        result = HashService.calculate_hashes(path, self.progress_cb, self.cancel_event)

        self.assertTrue(result.success)
        self.assertIn(100, self.progress_values,
                      "Expected final 100% tick even for zero-byte file.")

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_zero_byte_file(self):
        """A zero-byte file should succeed with valid (empty-content) digests."""
        path = self._make_temp_file(b"")

        # Empty hashes are well-defined constants
        expected_md5    = hashlib.md5(b"", usedforsecurity=False).hexdigest()
        expected_sha256 = hashlib.sha256(b"").hexdigest()

        result = HashService.calculate_hashes(path, self.progress_cb, self.cancel_event)

        self.assertTrue(result.success)
        self.assertEqual(result.md5, expected_md5)
        self.assertEqual(result.sha256, expected_sha256)

    def test_single_chunk_exact_boundary(self):
        """File exactly CHUNK_SIZE bytes — boundary condition for the read loop."""
        content = os.urandom(HashService.CHUNK_SIZE)
        path = self._make_temp_file(content)

        result = HashService.calculate_hashes(path, self.progress_cb, self.cancel_event)

        self.assertTrue(result.success)
        self.assertEqual(result.md5,
                         hashlib.md5(content, usedforsecurity=False).hexdigest())

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_missing_file_returns_failure(self):
        """A non-existent path must return success=False with a descriptive error_message."""
        result = HashService.calculate_hashes(
            "/nonexistent/path/image.e01", self.progress_cb, self.cancel_event
        )

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_message)
        self.assertIn("not found", result.error_message.lower())
        self.assertEqual(result.md5, "")
        self.assertEqual(result.sha256, "")

    def test_elapsed_time_is_positive(self):
        """Elapsed time on a successful hash must be a positive float."""
        content = b"timing test"
        path = self._make_temp_file(content)

        result = HashService.calculate_hashes(path, self.progress_cb, self.cancel_event)

        self.assertTrue(result.success)
        self.assertGreater(result.elapsed_time, 0.0)

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def test_cancel_before_start_returns_failure(self):
        """Setting the cancel event before calling calculate_hashes aborts immediately."""
        content = os.urandom(HashService.CHUNK_SIZE * 5)
        path = self._make_temp_file(content)

        self.cancel_event.set()   # Signal cancel before invocation
        result = HashService.calculate_hashes(path, self.progress_cb, self.cancel_event)

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_message)
        self.assertIn("aborted", result.error_message.lower())
        self.assertEqual(result.md5, "")

    def test_cancel_mid_stream_returns_failure_with_elapsed_time(self):
        """Setting the cancel event mid-stream returns failure and records actual elapsed time."""
        # Create a file large enough that we get at least one full chunk before cancelling
        content = os.urandom(HashService.CHUNK_SIZE * 4)
        path = self._make_temp_file(content)

        chunks_seen = []

        def cancelling_cb(pct: int):
            chunks_seen.append(pct)
            # Cancel after the first progress tick (i.e. after first chunk read)
            if len(chunks_seen) == 1:
                self.cancel_event.set()

        result = HashService.calculate_hashes(path, cancelling_cb, self.cancel_event)

        self.assertFalse(result.success)
        self.assertEqual(result.md5, "")
        # Elapsed time must be recorded (not 0.0 as the old bug had)
        self.assertGreater(result.elapsed_time, 0.0)
        self.assertIsNotNone(result.error_message)


class TestPreflightValidator(unittest.TestCase):
    """Unit tests for PreflightValidator covering all Phase 10 validation scenarios."""

    # ------------------------------------------------------------------
    # Shared fixtures
    # ------------------------------------------------------------------

    def setUp(self):
        """Build a minimal but real RAW->VMDK ConversionPlan for use in tests."""
        self.plan = ConversionPlanner.plan_conversion(
            FileFormat.RAW, FileFormat.VMDK,
            input_path="/fake/source.raw",
            output_path="/fake/dest/output.vmdk",
        )

    def _make_source(self, content: bytes = b"\x00" * 1024) -> str:
        """Creates a temporary source file and registers cleanup."""
        fd, path = tempfile.mkstemp(suffix=".raw")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(content)
        self.addCleanup(lambda p=path: os.remove(p) if os.path.exists(p) else None)
        return path

    def _make_dest_dir(self) -> str:
        """Creates a temporary destination directory and registers cleanup."""
        d = tempfile.mkdtemp()
        self.addCleanup(lambda p=d: __import__('shutil').rmtree(p, ignore_errors=True))
        return d

    # ------------------------------------------------------------------
    # Source file checks
    # ------------------------------------------------------------------

    def test_missing_source_returns_error(self):
        """SOURCE_NOT_FOUND error when source file does not exist."""
        dest = self._make_dest_dir()
        result = PreflightValidator.validate(
            self.plan, "/nonexistent/source.raw", dest, "out.vmdk"
        )
        self.assertFalse(result.passed)
        codes = [m.code for m in result.messages]
        self.assertIn(ValidationCode.SOURCE_NOT_FOUND, codes)

    def test_empty_source_emits_warning(self):
        """SOURCE_EMPTY warning (not error) when source file is 0 bytes."""
        src = self._make_source(b"")
        dest = self._make_dest_dir()
        result = PreflightValidator.validate(self.plan, src, dest, "out.vmdk")
        # Should not be a hard error
        error_codes = [m.code for m in result.errors]
        self.assertNotIn(ValidationCode.SOURCE_NOT_FOUND, error_codes)
        warn_codes = [m.code for m in result.warnings]
        self.assertIn(ValidationCode.SOURCE_EMPTY, warn_codes)

    def test_source_not_readable_returns_error(self):
        """SOURCE_NOT_READABLE error when os.access reports the file is unreadable."""
        src = self._make_source(b"valid content")
        dest = self._make_dest_dir()
        with patch("os.access", return_value=False):
            result = PreflightValidator.validate(self.plan, src, dest, "out.vmdk")
        error_codes = [m.code for m in result.errors]
        self.assertIn(ValidationCode.SOURCE_NOT_READABLE, error_codes)

    # ------------------------------------------------------------------
    # Destination directory checks
    # ------------------------------------------------------------------

    def test_missing_dest_dir_returns_error(self):
        """DEST_DIR_NOT_FOUND / DEST_DIR_NOT_CREATABLE when dest is completely invalid."""
        src = self._make_source()
        result = PreflightValidator.validate(
            self.plan, src, "/Z:/completely/invalid/path/that/cannot/exist", "out.vmdk"
        )
        self.assertFalse(result.passed)
        codes = [m.code for m in result.messages]
        self.assertTrue(
            ValidationCode.DEST_DIR_NOT_FOUND in codes
            or ValidationCode.DEST_DIR_NOT_CREATABLE in codes,
            msg=f"Expected dest dir error, got codes: {codes}"
        )

    def test_non_writable_dest_returns_error(self):
        """DEST_DIR_NOT_WRITABLE error when ConversionService.verify_write_access fails."""
        src = self._make_source()
        dest = self._make_dest_dir()
        with patch(
            "app.core.preflight_validator.ConversionService.verify_write_access",
            return_value=False,
        ):
            result = PreflightValidator.validate(self.plan, src, dest, "out.vmdk")
        error_codes = [m.code for m in result.errors]
        self.assertIn(ValidationCode.DEST_DIR_NOT_WRITABLE, error_codes)

    # ------------------------------------------------------------------
    # Overwrite check
    # ------------------------------------------------------------------

    def test_existing_output_sets_overwrite_required(self):
        """OUTPUT_ALREADY_EXISTS warning and overwrite_required=True when output file exists."""
        src = self._make_source()
        dest = self._make_dest_dir()
        # Pre-create the output file
        out_path = Path(dest) / "out.vmdk"
        out_path.write_bytes(b"existing")

        result = PreflightValidator.validate(
            self.plan, src, dest, "out.vmdk", overwrite_confirmed=False
        )
        self.assertTrue(result.overwrite_required)
        warn_codes = [m.code for m in result.warnings]
        self.assertIn(ValidationCode.OUTPUT_ALREADY_EXISTS, warn_codes)

    def test_overwrite_confirmed_suppresses_flag(self):
        """overwrite_confirmed=True suppresses the OUTPUT_ALREADY_EXISTS flag."""
        src = self._make_source()
        dest = self._make_dest_dir()
        out_path = Path(dest) / "out.vmdk"
        out_path.write_bytes(b"existing")

        result = PreflightValidator.validate(
            self.plan, src, dest, "out.vmdk", overwrite_confirmed=True
        )
        self.assertFalse(result.overwrite_required)
        codes = [m.code for m in result.messages]
        self.assertNotIn(ValidationCode.OUTPUT_ALREADY_EXISTS, codes)

    # ------------------------------------------------------------------
    # Disk space checks
    # ------------------------------------------------------------------

    def test_disk_space_pass(self):
        """No INSUFFICIENT_DISK_SPACE error when free space is ample."""
        src = self._make_source(b"x" * 1024)  # 1 KB
        dest = self._make_dest_dir()
        # Mock 10 GB available
        mock_usage = __import__('collections').namedtuple('DU', ['total','used','free'])
        with patch("shutil.disk_usage", return_value=mock_usage(10**10, 0, 10**10)):
            result = PreflightValidator.validate(self.plan, src, dest, "out.vmdk")
        error_codes = [m.code for m in result.errors]
        self.assertNotIn(ValidationCode.INSUFFICIENT_DISK_SPACE, error_codes)

    def test_disk_space_fail(self):
        """INSUFFICIENT_DISK_SPACE error when free space is below the estimate."""
        src = self._make_source(b"x" * (10 * 1024 * 1024))  # 10 MB source
        dest = self._make_dest_dir()
        # Mock only 1 KB available — guaranteed to be less than the estimate
        mock_usage = __import__('collections').namedtuple('DU', ['total','used','free'])
        with patch("shutil.disk_usage", return_value=mock_usage(10**10, 0, 1024)):
            result = PreflightValidator.validate(self.plan, src, dest, "out.vmdk")
        error_codes = [m.code for m in result.errors]
        self.assertIn(ValidationCode.INSUFFICIENT_DISK_SPACE, error_codes)
        self.assertFalse(result.passed)

    # ------------------------------------------------------------------
    # Dry run
    # ------------------------------------------------------------------

    def test_dry_run_returns_commands_without_execution(self):
        """dry_run() returns a DryRunResult with planned_commands and no subprocess call."""
        src = self._make_source()
        dest = self._make_dest_dir()

        # Ensure no subprocess is invoked
        with patch("subprocess.Popen") as mock_popen:
            dry = PreflightValidator.dry_run(self.plan, src, dest, "out.vmdk")
            mock_popen.assert_not_called()

        self.assertIsInstance(dry, DryRunResult)
        self.assertIsInstance(dry.planned_commands, list)
        self.assertEqual(len(dry.planned_commands), self.plan.total_steps)
        # Each command must be a non-empty list of strings
        for cmd in dry.planned_commands:
            self.assertIsInstance(cmd, list)
            self.assertTrue(len(cmd) > 0)
            self.assertIsInstance(cmd[0], str)

    def test_dry_run_with_missing_source_has_passed_false(self):
        """dry_run() with an invalid source produces passed=False."""
        dest = self._make_dest_dir()
        dry = PreflightValidator.dry_run(
            self.plan, "/nonexistent/file.raw", dest, "out.vmdk"
        )
        self.assertFalse(dry.passed)
        self.assertFalse(dry.validation.passed)

    # ------------------------------------------------------------------
    # Structured result integrity
    # ------------------------------------------------------------------

    def test_validation_result_structure(self):
        """ValidationResult fields are populated correctly on a passing run."""
        src = self._make_source(b"x" * 4096)
        dest = self._make_dest_dir()
        mock_usage = __import__('collections').namedtuple('DU', ['total','used','free'])
        with patch("shutil.disk_usage", return_value=mock_usage(10**10, 0, 10**10)):
            result = PreflightValidator.validate(self.plan, src, dest, "out.vmdk")

        self.assertTrue(result.passed)
        self.assertIsInstance(result.messages, list)
        self.assertFalse(result.overwrite_required)
        # space_estimate must be an EstimatedSpaceRequirement
        self.assertIsNotNone(result.space_estimate)
        se = result.space_estimate
        self.assertGreater(se.source_size_bytes, 0)
        self.assertGreater(se.total_required_bytes, 0)
        self.assertTrue(se.has_enough_space)

    def test_estimate_space_heuristic(self):
        """estimate_space total = raw_estimate + 15% safety margin."""
        source_size = 1_000_000  # 1 MB
        mock_usage = __import__('collections').namedtuple('DU', ['total','used','free'])
        with patch("shutil.disk_usage", return_value=mock_usage(10**10, 0, 10**10)):
            se = PreflightValidator.estimate_space(self.plan, source_size, "/tmp")

        expected_raw = source_size * (self.plan.total_steps + 1)
        expected_margin = int(expected_raw * 0.15)
        self.assertEqual(se.raw_estimate_bytes, expected_raw)
        self.assertEqual(se.safety_margin_bytes, expected_margin)
        self.assertEqual(se.total_required_bytes, expected_raw + expected_margin)


if __name__ == "__main__":
    unittest.main()
