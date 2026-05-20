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
