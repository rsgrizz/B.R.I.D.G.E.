# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.1
# Date: 5/20/2026
# Purpose: Shared data structures, enums, and dataclasses representing domain models.

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List

class FileFormat(Enum):
    E01 = "E01"
    EX01 = "Ex01"
    DMG = "DMG"
    RAW = "RAW"
    VMDK = "VMDK"
    VHD = "VHD"
    VHDX = "VHDX"
    QCOW2 = "QCOW2"
    UNKNOWN = "UNKNOWN"

class PathRisk(Enum):
    STABLE = "STABLE"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNSUPPORTED = "UNSUPPORTED"

class PlanConfidence(Enum):
    HIGH = "HIGH"
    LOW = "LOW"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNSUPPORTED = "UNSUPPORTED"

class DetectionMethod(Enum):
    SIGNATURE = "SIGNATURE"
    EXTENSION = "EXTENSION"
    UNKNOWN = "UNKNOWN"

class PlannerError(Exception):
    """Exception raised when the conversion planner cannot find a valid path or encounters an issue."""
    pass

@dataclass(frozen=True)
class DetectionResult:
    format: FileFormat
    method: DetectionMethod
    confidence: str              # 'High' for magic bytes, 'Medium' for extensions, 'Low' for unknown/default

@dataclass(frozen=True)
class ToolSpec:
    backend_tool: str
    command_template_tokens: List[str]
    notes: str = ""

@dataclass(frozen=True)
class ConversionEdge:
    source: FileFormat
    target: FileFormat
    backend_tool: str
    command_template_tokens: List[str]
    experimental: bool = False
    notes: str = ""
    weight: float = 1.0

@dataclass(frozen=True)
class ConversionStep:
    step_num: int
    source_format: FileFormat
    target_format: FileFormat
    command_args: List[str]
    input_file: str
    output_file: str
    backend_tool: str
    command_template_tokens: List[str]
    notes: str = ""
    is_intermediate: bool = False
    experimental: bool = False
    risk: PathRisk = PathRisk.STABLE

@dataclass(frozen=True)
class ConversionPlan:
    steps: List[ConversionStep]
    estimated_temp_bytes: int
    total_steps: int = field(init=False)
    has_experimental: bool = field(init=False)
    confidence: PlanConfidence = field(init=False)

    def __post_init__(self):
        # We bypass frozen restriction during initialization
        object.__setattr__(self, 'total_steps', len(self.steps))
        has_exp = any(s.risk == PathRisk.EXPERIMENTAL or s.experimental for s in self.steps)
        object.__setattr__(self, 'has_experimental', has_exp)
        conf = PlanConfidence.EXPERIMENTAL if has_exp else PlanConfidence.HIGH
        object.__setattr__(self, 'confidence', conf)

@dataclass(frozen=True)
class ToolExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    elapsed_time_seconds: float
    success: bool
    cancelled: bool = False

@dataclass(frozen=True)
class HashResult:
    md5: str
    sha1: str
    sha256: str
    elapsed_time: float
    success: bool
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase 10 — Pre-flight Validation Models
# ---------------------------------------------------------------------------

class ValidationSeverity(Enum):
    """Severity level for a single validation finding."""
    ERROR   = "ERROR"      # Hard stop — conversion must not proceed
    WARNING = "WARNING"    # Soft check — user may acknowledge and continue
    INFO    = "INFO"       # Informational only


class ValidationCode(Enum):
    """Machine-readable codes for every distinct validation check."""
    SOURCE_NOT_FOUND          = "SOURCE_NOT_FOUND"
    SOURCE_NOT_READABLE       = "SOURCE_NOT_READABLE"
    SOURCE_EMPTY              = "SOURCE_EMPTY"
    DEST_DIR_NOT_FOUND        = "DEST_DIR_NOT_FOUND"
    DEST_DIR_NOT_CREATABLE    = "DEST_DIR_NOT_CREATABLE"
    DEST_DIR_NOT_WRITABLE     = "DEST_DIR_NOT_WRITABLE"
    OUTPUT_ALREADY_EXISTS     = "OUTPUT_ALREADY_EXISTS"
    INTERMEDIATE_PATH_INVALID = "INTERMEDIATE_PATH_INVALID"
    REQUIRED_TOOL_MISSING     = "REQUIRED_TOOL_MISSING"
    INSUFFICIENT_DISK_SPACE   = "INSUFFICIENT_DISK_SPACE"
    DISK_SPACE_LOW_WARNING    = "DISK_SPACE_LOW_WARNING"
    NO_PLAN                   = "NO_PLAN"
    OK                        = "OK"


@dataclass(frozen=True)
class ValidationMessage:
    """A single finding produced by PreflightValidator."""
    severity: ValidationSeverity
    code:     ValidationCode
    message:  str              # Human-readable description


@dataclass(frozen=True)
class EstimatedSpaceRequirement:
    """Space estimate for a planned conversion pipeline."""
    source_size_bytes:      int    # Actual source file size on disk
    num_steps:              int    # Number of ConversionStep objects in the plan
    raw_estimate_bytes:     int    # source_size × (steps + 1) before margin
    safety_margin_bytes:    int    # The buffer added on top
    total_required_bytes:   int    # raw_estimate + safety_margin
    available_bytes:        int    # shutil.disk_usage(dest_path).free
    has_enough_space:       bool   # total_required_bytes <= available_bytes


@dataclass(frozen=True)
class ValidationResult:
    """Structured outcome of a full pre-flight validation pass.

    ``passed`` is True only when there are no ERROR-severity messages.
    WARNING messages are collected but do not block execution on their own.
    ``overwrite_required`` signals that the GUI must ask the user for
    explicit permission before proceeding.
    """
    passed:              bool
    messages:            List[ValidationMessage]
    overwrite_required:  bool                       = False
    space_estimate:      Optional[object]           = None   # EstimatedSpaceRequirement | None

    @property
    def errors(self) -> List[ValidationMessage]:
        return [m for m in self.messages if m.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationMessage]:
        return [m for m in self.messages if m.severity == ValidationSeverity.WARNING]


@dataclass(frozen=True)
class DryRunResult:
    """Result of a dry-run execution — validation was performed but no tool was invoked."""
    validation:        ValidationResult
    plan_report:       str               # generate_dry_run_report() output
    planned_commands:  List[List[str]]   # Each step's fully-resolved command_args
    passed:            bool              # True only if validation.passed is True
