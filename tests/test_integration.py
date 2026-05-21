# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.1
# Date: 5/21/2026
# Purpose: Integration tests for ConversionWorker signal emission, pipeline cancellation, progress monotonicity, and cleanup behavior under Qt event loop.

import unittest
from unittest.mock import patch, MagicMock
from PySide6.QtCore import QCoreApplication
from app.core.models import FileFormat, ToolExecutionResult
from app.core.conversion_planner import ConversionPlanner
from app.workers.conversion_worker import ConversionWorker

class TestConversionWorkerIntegration(unittest.TestCase):
    """Integration test suite for ConversionWorker pipeline execution."""

    @classmethod
    def setUpClass(cls):
        # Initialize QCoreApplication once for the test run to satisfy Qt signal/slot event loop context requirements.
        cls.app = QCoreApplication.instance()
        if cls.app is None:
            cls.app = QCoreApplication([])

    def test_successful_multistep_signal_order(self):
        """Successful multi-step pipeline emits signals in the expected sequential order."""
        plan = ConversionPlanner.plan_conversion(
            FileFormat.E01,
            FileFormat.VHD,
            input_path="/fake/source.e01",
            output_path="/fake/dest/output.vhd"
        )
        self.assertEqual(plan.total_steps, 2)

        worker = ConversionWorker(plan)

        signals = []
        worker.conversion_started.connect(lambda p: signals.append(("conversion_started", p)))
        worker.step_started.connect(lambda s: signals.append(("step_started", s)))
        worker.progress_updated.connect(lambda p: signals.append(("progress_updated", p)))
        worker.log_received.connect(lambda l: signals.append(("log_received", l)))
        worker.step_completed.connect(lambda s: signals.append(("step_completed", s)))
        worker.conversion_completed.connect(lambda ok: signals.append(("conversion_completed", ok)))
        worker.conversion_failed.connect(lambda err: signals.append(("conversion_failed", err)))
        worker.cancelled.connect(lambda: signals.append(("cancelled",)))

        def mock_run(cmd, log_cb, cancel_event):
            log_cb("Status: at 50.0%.")
            return ToolExecutionResult(
                exit_code=0,
                stdout="Progress: 50%",
                stderr="",
                elapsed_time_seconds=0.1,
                success=True,
                cancelled=False
            )

        with patch('app.workers.conversion_worker.ToolRunner.run_command', side_effect=mock_run):
            worker.run()

        event_types = [s[0] for s in signals]

        # Verify main lifecycle signals are in the expected sequence
        self.assertEqual(event_types[0], "conversion_started")
        self.assertEqual(signals[0][1], plan)

        # Find first occurrences of step starts and completions
        idx_step1_start = event_types.index("step_started")
        self.assertEqual(signals[idx_step1_start][1], 1)

        idx_step1_complete = event_types.index("step_completed")
        self.assertEqual(signals[idx_step1_complete][1], 1)
        self.assertGreater(idx_step1_complete, idx_step1_start)

        # Check step 2 is after step 1 completion
        step2_starts = [i for i, x in enumerate(signals) if x[0] == "step_started" and x[1] == 2]
        self.assertTrue(len(step2_starts) > 0)
        idx_step2_start = step2_starts[0]
        self.assertGreater(idx_step2_start, idx_step1_complete)

        step2_completes = [i for i, x in enumerate(signals) if x[0] == "step_completed" and x[1] == 2]
        self.assertTrue(len(step2_completes) > 0)
        idx_step2_complete = step2_completes[0]
        self.assertGreater(idx_step2_complete, idx_step2_start)

        # conversion_completed(True) must be the final outcome
        idx_completed = event_types.index("conversion_completed")
        self.assertEqual(signals[idx_completed][1], True)
        self.assertGreater(idx_completed, idx_step2_complete)

        # No errors or cancellations
        self.assertNotIn("conversion_failed", event_types)
        self.assertNotIn("cancelled", event_types)

    def test_step2_failure_emits_failed_not_success(self):
        """Step 2 failure emits conversion_failed and suppresses success emission."""
        plan = ConversionPlanner.plan_conversion(
            FileFormat.E01,
            FileFormat.VHD,
            input_path="/fake/source.e01",
            output_path="/fake/dest/output.vhd"
        )
        worker = ConversionWorker(plan)

        signals = []
        worker.conversion_started.connect(lambda p: signals.append(("conversion_started", p)))
        worker.step_started.connect(lambda s: signals.append(("step_started", s)))
        worker.step_completed.connect(lambda s: signals.append(("step_completed", s)))
        worker.conversion_completed.connect(lambda ok: signals.append(("conversion_completed", ok)))
        worker.conversion_failed.connect(lambda err: signals.append(("conversion_failed", err)))

        def mock_run(cmd, log_cb, cancel_event):
            # Check if this is step 1 (converting to raw) or step 2 (converting to vhd)
            is_step2 = any("vhd" in str(arg).lower() for arg in cmd)
            if is_step2:
                return ToolExecutionResult(
                    exit_code=1,
                    stdout="",
                    stderr="Failed to write VHD footer.",
                    elapsed_time_seconds=0.2,
                    success=False,
                    cancelled=False
                )
            return ToolExecutionResult(
                exit_code=0,
                stdout="Step 1 complete.",
                stderr="",
                elapsed_time_seconds=0.1,
                success=True,
                cancelled=False
            )

        with patch('app.workers.conversion_worker.ToolRunner.run_command', side_effect=mock_run):
            worker.run()

        event_types = [s[0] for s in signals]

        # Step 1 should start and complete
        self.assertIn("step_started", event_types)
        self.assertIn("step_completed", event_types)
        
        # Step 2 should start but NOT complete
        step_completed_payloads = [s[1] for s in signals if s[0] == "step_completed"]
        self.assertIn(1, step_completed_payloads)
        self.assertNotIn(2, step_completed_payloads)

        # conversion_failed must be emitted
        self.assertIn("conversion_failed", event_types)
        failed_payloads = [s[1] for s in signals if s[0] == "conversion_failed"]
        self.assertTrue(any("failed with exit code 1" in str(p) for p in failed_payloads))

        # conversion_completed(False) must be emitted, and conversion_completed(True) must NOT be emitted
        completed_payloads = [s[1] for s in signals if s[0] == "conversion_completed"]
        self.assertIn(False, completed_payloads)
        self.assertNotIn(True, completed_payloads)

    def test_mid_pipeline_cancellation(self):
        """Mid-pipeline cancellation stops execution and emits cancelled states."""
        plan = ConversionPlanner.plan_conversion(
            FileFormat.E01,
            FileFormat.VHD,
            input_path="/fake/source.e01",
            output_path="/fake/dest/output.vhd"
        )
        worker = ConversionWorker(plan)

        signals = []
        worker.conversion_started.connect(lambda p: signals.append(("conversion_started", p)))
        worker.step_started.connect(lambda s: signals.append(("step_started", s)))
        worker.step_completed.connect(lambda s: signals.append(("step_completed", s)))
        worker.cancelled.connect(lambda: signals.append(("cancelled",)))
        worker.conversion_completed.connect(lambda ok: signals.append(("conversion_completed", ok)))

        def mock_run(cmd, log_cb, cancel_event):
            # Simulate step 1 being cancelled mid-run
            return ToolExecutionResult(
                exit_code=-1,
                stdout="",
                stderr="User interrupted execution.",
                elapsed_time_seconds=0.1,
                success=False,
                cancelled=True
            )

        with patch('app.workers.conversion_worker.ToolRunner.run_command', side_effect=mock_run):
            worker.run()

        event_types = [s[0] for s in signals]

        self.assertIn("conversion_started", event_types)
        self.assertIn("step_started", event_types)
        self.assertNotIn("step_completed", event_types)
        self.assertIn("cancelled", event_types)
        
        # conversion_completed(False) is emitted
        completed_payloads = [s[1] for s in signals if s[0] == "conversion_completed"]
        self.assertIn(False, completed_payloads)
        self.assertNotIn(True, completed_payloads)

    def test_pre_step_cancellation(self):
        """Pre-step cancellation check intercepts loop and halts before second step starts."""
        plan = ConversionPlanner.plan_conversion(
            FileFormat.E01,
            FileFormat.VHD,
            input_path="/fake/source.e01",
            output_path="/fake/dest/output.vhd"
        )
        worker = ConversionWorker(plan)

        signals = []
        worker.conversion_started.connect(lambda p: signals.append(("conversion_started", p)))
        worker.step_started.connect(lambda s: signals.append(("step_started", s)))
        worker.step_completed.connect(lambda s: signals.append(("step_completed", s)))
        worker.cancelled.connect(lambda: signals.append(("cancelled",)))
        worker.conversion_completed.connect(lambda ok: signals.append(("conversion_completed", ok)))

        def mock_run(cmd, log_cb, cancel_event):
            # Step 1 runs successfully, but sets the worker cancellation event
            worker.cancel()
            return ToolExecutionResult(
                exit_code=0,
                stdout="Step 1 success",
                stderr="",
                elapsed_time_seconds=0.1,
                success=True,
                cancelled=False
            )

        with patch('app.workers.conversion_worker.ToolRunner.run_command', side_effect=mock_run):
            worker.run()

        event_types = [s[0] for s in signals]

        # Step 1 should start and complete
        step_started_payloads = [s[1] for s in signals if s[0] == "step_started"]
        self.assertIn(1, step_started_payloads)
        self.assertNotIn(2, step_started_payloads)

        step_completed_payloads = [s[1] for s in signals if s[0] == "step_completed"]
        self.assertIn(1, step_completed_payloads)

        # cancelled signal must be emitted pre-step 2
        self.assertIn("cancelled", event_types)
        
        completed_payloads = [s[1] for s in signals if s[0] == "conversion_completed"]
        self.assertIn(False, completed_payloads)

    def test_cleanup_invoked_on_failure(self):
        """Intermediate files are removed during post-conversion cleanup on failure."""
        plan = ConversionPlanner.plan_conversion(
            FileFormat.E01,
            FileFormat.VHD,
            input_path="/fake/source.e01",
            output_path="/fake/dest/output.vhd"
        )
        worker = ConversionWorker(plan)

        # Find the intermediate file path from the steps
        intermediate_path = next(s.output_file for s in plan.steps if s.is_intermediate)
        self.assertIsNotNone(intermediate_path)

        def mock_run(cmd, log_cb, cancel_event):
            # Step 1 succeeds, Step 2 fails
            is_step2 = any("vhd" in str(arg).lower() for arg in cmd)
            if is_step2:
                return ToolExecutionResult(
                    exit_code=1,
                    stdout="",
                    stderr="Failure",
                    elapsed_time_seconds=0.1,
                    success=False
                )
            return ToolExecutionResult(
                exit_code=0,
                stdout="Success",
                stderr="",
                elapsed_time_seconds=0.1,
                success=True
            )

        # We will mock os.path.exists to return True specifically for our intermediate path,
        # and mock os.remove to spy on what got deleted.
        exists_mock = MagicMock(side_effect=lambda path: path == intermediate_path)
        remove_mock = MagicMock()

        with patch('app.workers.conversion_worker.ToolRunner.run_command', side_effect=mock_run), \
             patch('app.workers.conversion_worker.os.path.exists', exists_mock), \
             patch('app.workers.conversion_worker.os.remove', remove_mock):
            worker.run()

        # Verify that existence of the intermediate file was checked and that it was removed
        exists_mock.assert_any_call(intermediate_path)
        remove_mock.assert_called_once_with(intermediate_path)

    def test_progress_non_regressive(self):
        """Global progress updates emitted are monotonically non-decreasing (non-regressive) across steps."""
        plan = ConversionPlanner.plan_conversion(
            FileFormat.E01,
            FileFormat.VHD,
            input_path="/fake/source.e01",
            output_path="/fake/dest/output.vhd"
        )
        worker = ConversionWorker(plan)

        progress_values = []
        worker.progress_updated.connect(progress_values.append)

        def mock_run(cmd, log_cb, cancel_event):
            # Emit progress increments during step execution
            log_cb("(10.00/100%)")
            log_cb("(50.00/100%)")
            log_cb("(90.00/100%)")
            return ToolExecutionResult(
                exit_code=0,
                stdout="Success",
                stderr="",
                elapsed_time_seconds=0.1,
                success=True
            )

        with patch('app.workers.conversion_worker.ToolRunner.run_command', side_effect=mock_run):
            worker.run()

        self.assertTrue(len(progress_values) > 0)
        # Ensure that every progress value is greater than or equal to the previous value
        for i in range(1, len(progress_values)):
            self.assertGreaterEqual(
                progress_values[i],
                progress_values[i - 1],
                f"Progress regressed at index {i}: {progress_values[i]} < {progress_values[i-1]}"
            )

    def test_log_includes_step_context(self):
        """Worker log emissions contain detailed step-identifying context for debugging and reporting."""
        plan = ConversionPlanner.plan_conversion(
            FileFormat.E01,
            FileFormat.VHD,
            input_path="/fake/source.e01",
            output_path="/fake/dest/output.vhd"
        )
        worker = ConversionWorker(plan)

        logs = []
        worker.log_received.connect(logs.append)

        def mock_run(cmd, log_cb, cancel_event):
            return ToolExecutionResult(
                exit_code=0,
                stdout="",
                stderr="",
                elapsed_time_seconds=0.1,
                success=True
            )

        with patch('app.workers.conversion_worker.ToolRunner.run_command', side_effect=mock_run):
            worker.run()

        # Check that there are logs referencing Step 1 and Step 2
        step1_found = any("Step 1/2" in log or "Step 1" in log for log in logs)
        step2_found = any("Step 2/2" in log or "Step 2" in log for log in logs)

        self.assertTrue(step1_found, "Logs did not contain Step 1 context.")
        self.assertTrue(step2_found, "Logs did not contain Step 2 context.")
