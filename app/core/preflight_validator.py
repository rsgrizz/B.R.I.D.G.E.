# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.1
# Date: 5/21/2026
# Purpose: Structured pre-flight validation layer for conversion safety checks.

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from app.core.models import (
    ConversionPlan,
    DryRunResult,
    EstimatedSpaceRequirement,
    ValidationCode,
    ValidationMessage,
    ValidationResult,
    ValidationSeverity,
)
from app.core.conversion_service import ConversionService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

# Fraction of the raw space estimate added as a safety buffer.
# 0.15 = 15 % overhead on top of the estimated bytes needed.
SAFETY_MARGIN_FACTOR: float = 0.15

# Minimum source-file size below which we emit a SOURCE_EMPTY warning.
# Forensic images are virtually never legitimately this small.
MIN_SOURCE_SIZE_BYTES: int = 512


class PreflightValidator:
    """Qt-free validation service.  All methods are static so they can be
    called from unit tests without instantiation or any GUI context.

    Validation is split into two passes:
      1. :meth:`validate` — performs all checks and returns a
         :class:`ValidationResult`.  Hard failures set ``passed=False``.
         An overwrite-required flag is set rather than blocking here so
         that the GUI can present the dialog and then re-call
         :meth:`validate_after_overwrite_confirmed` if the user accepts.
      2. :meth:`dry_run` — calls :meth:`validate` then builds a
         :class:`DryRunResult` without executing any subprocess.
    """

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    @staticmethod
    def validate(
        plan: Optional[ConversionPlan],
        source_path: str,
        dest_dir: str,
        output_filename: str,
        *,
        overwrite_confirmed: bool = False,
    ) -> ValidationResult:
        """Run the full pre-flight checklist and return a structured result.

        Parameters
        ----------
        plan:
            The :class:`ConversionPlan` produced by the planner.  If
            ``None`` an immediate ERROR is returned.
        source_path:
            Absolute path to the source evidence/image file.
        dest_dir:
            Absolute path to the destination directory.
        output_filename:
            Bare filename (with extension) of the final output file.
        overwrite_confirmed:
            Pass ``True`` when the user has already acknowledged that an
            existing output file may be overwritten.  This suppresses the
            ``OUTPUT_ALREADY_EXISTS`` flag.
        """
        messages: list[ValidationMessage] = []

        # ---- 1. Plan must exist ----------------------------------------
        if plan is None:
            messages.append(ValidationMessage(
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.NO_PLAN,
                message="No conversion plan is available. Select a source and target format first.",
            ))
            return ValidationResult(passed=False, messages=messages)

        # ---- 2. Source file existence ----------------------------------
        src = Path(source_path) if source_path else None
        source_size_bytes = 0

        if not source_path or not src.exists():
            messages.append(ValidationMessage(
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.SOURCE_NOT_FOUND,
                message=f"Source file not found: {source_path!r}",
            ))
        elif not src.is_file():
            messages.append(ValidationMessage(
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.SOURCE_NOT_FOUND,
                message=f"Source path is not a regular file: {source_path!r}",
            ))
        else:
            # ---- 3. Source readability ---------------------------------
            if not os.access(src, os.R_OK):
                messages.append(ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.SOURCE_NOT_READABLE,
                    message=f"Source file exists but is not readable (permission denied): {source_path!r}",
                ))
            else:
                try:
                    source_size_bytes = src.stat().st_size
                except OSError as exc:
                    messages.append(ValidationMessage(
                        severity=ValidationSeverity.ERROR,
                        code=ValidationCode.SOURCE_NOT_READABLE,
                        message=f"Cannot read source file metadata: {exc}",
                    ))

            # ---- 4. Source non-empty check (warning only) --------------
            if source_size_bytes == 0:
                messages.append(ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    code=ValidationCode.SOURCE_EMPTY,
                    message=(
                        "Source file reports zero bytes. This may indicate a corrupt, "
                        "sparse, or invalid forensic image."
                    ),
                ))
            elif source_size_bytes < MIN_SOURCE_SIZE_BYTES:
                messages.append(ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    code=ValidationCode.SOURCE_EMPTY,
                    message=(
                        f"Source file is unusually small ({source_size_bytes} bytes). "
                        "Verify this is a valid image before proceeding."
                    ),
                ))

        # ---- 5. Destination directory ----------------------------------
        dest = Path(dest_dir) if dest_dir else None

        if not dest_dir:
            messages.append(ValidationMessage(
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.DEST_DIR_NOT_FOUND,
                message="No destination directory has been selected.",
            ))
        elif not dest.exists():
            # Attempt to determine whether the parent chain is creatable
            creatable = PreflightValidator._can_create_dir(dest)
            if creatable:
                messages.append(ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    code=ValidationCode.DEST_DIR_NOT_FOUND,
                    message=(
                        f"Destination directory does not exist and will be created: {dest_dir!r}"
                    ),
                ))
                # Try to create it now so subsequent checks work
                try:
                    dest.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Pre-flight: created destination directory: {dest_dir}")
                except OSError as exc:
                    messages.append(ValidationMessage(
                        severity=ValidationSeverity.ERROR,
                        code=ValidationCode.DEST_DIR_NOT_CREATABLE,
                        message=f"Could not create destination directory: {exc}",
                    ))
            else:
                messages.append(ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.DEST_DIR_NOT_CREATABLE,
                    message=(
                        f"Destination directory does not exist and cannot be created: {dest_dir!r}"
                    ),
                ))

        # ---- 6. Write access on destination ----------------------------
        if dest and dest.exists():
            if not ConversionService.verify_write_access(str(dest)):
                messages.append(ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.DEST_DIR_NOT_WRITABLE,
                    message=f"Destination directory is not writable: {dest_dir!r}",
                ))

        # ---- 7. Output file overwrite check ----------------------------
        overwrite_required = False
        output_path = (dest / output_filename) if (dest and output_filename) else None

        if output_path and output_path.exists() and not overwrite_confirmed:
            overwrite_required = True
            messages.append(ValidationMessage(
                severity=ValidationSeverity.WARNING,
                code=ValidationCode.OUTPUT_ALREADY_EXISTS,
                message=f"Output file already exists and will be overwritten: {output_path!r}",
            ))

        # ---- 8. Intermediate path validation ---------------------------
        for step in plan.steps:
            if step.is_intermediate and step.output_file:
                inter_path = Path(step.output_file)
                inter_dir = inter_path.parent
                if not inter_dir.exists():
                    try:
                        inter_dir.mkdir(parents=True, exist_ok=True)
                    except OSError as exc:
                        messages.append(ValidationMessage(
                            severity=ValidationSeverity.ERROR,
                            code=ValidationCode.INTERMEDIATE_PATH_INVALID,
                            message=(
                                f"Cannot create directory for intermediate file "
                                f"{step.output_file!r}: {exc}"
                            ),
                        ))

        # ---- 9. Disk space check ---------------------------------------
        space_estimate: Optional[EstimatedSpaceRequirement] = None
        check_path = dest or (output_path.parent if output_path else None)

        if check_path and check_path.exists():
            space_estimate = PreflightValidator.estimate_space(
                plan, source_size_bytes, str(check_path)
            )
            if not space_estimate.has_enough_space:
                required_gb = space_estimate.total_required_bytes / (1024 ** 3)
                available_gb = space_estimate.available_bytes / (1024 ** 3)
                messages.append(ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INSUFFICIENT_DISK_SPACE,
                    message=(
                        f"Insufficient disk space on destination volume. "
                        f"Required: {required_gb:.2f} GB  |  "
                        f"Available: {available_gb:.2f} GB"
                    ),
                ))
            else:
                # Warn if headroom is < 2 × safety margin (i.e. cutting it close)
                headroom = space_estimate.available_bytes - space_estimate.total_required_bytes
                if headroom < space_estimate.safety_margin_bytes * 2:
                    required_gb = space_estimate.total_required_bytes / (1024 ** 3)
                    available_gb = space_estimate.available_bytes / (1024 ** 3)
                    messages.append(ValidationMessage(
                        severity=ValidationSeverity.WARNING,
                        code=ValidationCode.DISK_SPACE_LOW_WARNING,
                        message=(
                            f"Disk space is tight. Required: {required_gb:.2f} GB  |  "
                            f"Available: {available_gb:.2f} GB. Proceed with caution."
                        ),
                    ))

        # ---- Compute final pass/fail -----------------------------------
        has_errors = any(m.severity == ValidationSeverity.ERROR for m in messages)
        passed = not has_errors

        if passed and not messages:
            messages.append(ValidationMessage(
                severity=ValidationSeverity.INFO,
                code=ValidationCode.OK,
                message="All pre-flight checks passed.",
            ))

        logger.info(
            f"Pre-flight validation complete — passed={passed}, "
            f"messages={len(messages)}, overwrite_required={overwrite_required}"
        )

        return ValidationResult(
            passed=passed,
            messages=messages,
            overwrite_required=overwrite_required,
            space_estimate=space_estimate,
        )

    @staticmethod
    def dry_run(
        plan: Optional[ConversionPlan],
        source_path: str,
        dest_dir: str,
        output_filename: str,
    ) -> DryRunResult:
        """Validate the full pipeline and return a :class:`DryRunResult`.

        No subprocess is invoked.  The caller can render the result in
        the GUI log pane to show the user exactly what *would* happen.
        """
        validation = PreflightValidator.validate(
            plan, source_path, dest_dir, output_filename
        )

        plan_report = ""
        planned_commands: list[list[str]] = []

        if plan is not None:
            plan_report = ConversionService.generate_dry_run_report(plan)
            planned_commands = [list(step.command_args) for step in plan.steps]

        return DryRunResult(
            validation=validation,
            plan_report=plan_report,
            planned_commands=planned_commands,
            passed=validation.passed,
        )

    # ------------------------------------------------------------------
    # Space estimation
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_space(
        plan: ConversionPlan,
        source_size_bytes: int,
        check_path: str,
    ) -> EstimatedSpaceRequirement:
        """Conservative space estimate for a conversion pipeline.

        Heuristic:
          raw_estimate = source_size × (total_steps + 1)
            - Each step may produce output roughly equal to the source size.
            - The +1 accounts for the final output itself.
          safety_margin = raw_estimate × SAFETY_MARGIN_FACTOR (15 %)
          total_required = raw_estimate + safety_margin

        If ``source_size_bytes`` is 0 the estimate cannot be computed
        meaningfully; we return ``has_enough_space=True`` to avoid a false
        block — the caller should have already flagged the empty-file warning.
        """
        if source_size_bytes == 0:
            return EstimatedSpaceRequirement(
                source_size_bytes=0,
                num_steps=plan.total_steps,
                raw_estimate_bytes=0,
                safety_margin_bytes=0,
                total_required_bytes=0,
                available_bytes=0,
                has_enough_space=True,
            )

        raw_estimate = source_size_bytes * (plan.total_steps + 1)
        safety_margin = int(raw_estimate * SAFETY_MARGIN_FACTOR)
        total_required = raw_estimate + safety_margin

        available = 0
        try:
            available = shutil.disk_usage(check_path).free
        except OSError as exc:
            logger.warning(f"Could not read disk usage for {check_path!r}: {exc}")

        return EstimatedSpaceRequirement(
            source_size_bytes=source_size_bytes,
            num_steps=plan.total_steps,
            raw_estimate_bytes=raw_estimate,
            safety_margin_bytes=safety_margin,
            total_required_bytes=total_required,
            available_bytes=available,
            has_enough_space=(available >= total_required),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _can_create_dir(path: Path) -> bool:
        """Walk up the path hierarchy to find the nearest existing ancestor
        and check whether it is writable by the current process.
        """
        candidate = path
        while candidate != candidate.parent:
            if candidate.exists():
                return os.access(candidate, os.W_OK)
            candidate = candidate.parent
        return False
