# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.3
# Date: 5/20/2026
# Purpose: Multi-step command execution pipeline running inside a dedicated background worker thread.

import logging
import os
import re
from threading import Event
from PySide6.QtCore import QThread, Signal
from app.core.models import ConversionPlan, ToolExecutionResult
from app.core.tool_runner import ToolRunner

logger = logging.getLogger(__name__)

# Pre-compiled progress regexes for supported tool output formats
# qemu-img: "(50.00/100%)"
_QEMU_PROGRESS_RE = re.compile(r'\((\d+(?:\.\d+)?)/100%\)')
# ewfexport: "Status: at 50.0%." or "50%" standalone
_EWF_PROGRESS_RE = re.compile(r'(\d+(?:\.\d+)?)\s*%')


def _parse_progress(line: str) -> int | None:
    """Attempts to extract an integer progress value (0-100) from a tool output line.
    Returns None if no recognisable pattern is found.
    """
    m = _QEMU_PROGRESS_RE.search(line)
    if m:
        return min(100, int(float(m.group(1))))
    m = _EWF_PROGRESS_RE.search(line)
    if m:
        return min(100, int(float(m.group(1))))
    return None


class ConversionWorker(QThread):
    """Asynchronous PySide6 thread worker that runs a multi-step ConversionPlan sequentially
    and propagates stdout/stderr logs and progress signals back to the UI.
    """

    # Thread communication signals (all consumed safely by the GUI main thread)
    conversion_started = Signal(object)   # Payload: ConversionPlan
    step_started = Signal(int)            # Payload: step_num
    progress_updated = Signal(int)        # Payload: overall percent (0-100)
    log_received = Signal(str)            # Payload: HTML-formatted log string
    step_completed = Signal(int)          # Payload: step_num
    conversion_completed = Signal(bool)   # Payload: success flag
    conversion_failed = Signal(str)       # Payload: error detail string
    cancelled = Signal()

    def __init__(self, plan: ConversionPlan, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.cancel_event = Event()

    def run(self):
        """Standard thread execution loop — runs each ConversionStep sequentially."""
        logger.info(
            f"Starting background conversion thread for plan containing "
            f"{self.plan.total_steps} step(s)."
        )
        self.conversion_started.emit(self.plan)

        success = True
        total_steps = self.plan.total_steps

        try:
            for step in self.plan.steps:
                # Pre-step cancellation check
                if self.cancel_event.is_set():
                    logger.warning("Conversion thread loop interrupted by cancellation event.")
                    self.cancelled.emit()
                    success = False
                    break

                self.step_started.emit(step.step_num)
                self.log_received.emit(
                    f"<b>[SYSTEM]: Beginning Step {step.step_num}/{total_steps} "
                    f"({step.source_format.value} ➔ {step.target_format.value})</b>"
                )
                self.log_received.emit(
                    f"<font color='#94a3b8'>[CMD]: {' '.join(step.command_args)}</font>"
                )

                # Base progress offset for this step (each step is an equal slice of 0-100)
                step_base = int(((step.step_num - 1) / total_steps) * 100)
                step_range = int(100 / total_steps)

                def local_log_cb(log_line: str, _base=step_base, _range=step_range):
                    """Real-time stdout/stderr forwarding with inline progress parsing."""
                    self.log_received.emit(log_line)
                    pct = _parse_progress(log_line)
                    if pct is not None:
                        # Map tool-local 0-100 into the global step slice
                        global_pct = _base + int((_range * pct) / 100)
                        self.progress_updated.emit(global_pct)

                logger.info(
                    f"Executing step {step.step_num} command: {' '.join(step.command_args)}"
                )

                result: ToolExecutionResult = ToolRunner.run_command(
                    step.command_args,
                    local_log_cb,
                    self.cancel_event
                )

                if not result.success:
                    if result.cancelled:
                        self.log_received.emit(
                            "<font color='orange'><b>[WARNING]: Step cancelled by investigator.</b></font>"
                        )
                        self.cancelled.emit()
                    else:
                        err_msg = (
                            f"Step {step.step_num} failed with exit code {result.exit_code}. "
                            f"Stderr: {result.stderr[:500]}"
                        )
                        self.log_received.emit(
                            f"<font color='red'><b>[CRITICAL ERROR]: {err_msg}</b></font>"
                        )
                        self.conversion_failed.emit(err_msg)
                    success = False
                    break

                # Emit the exact end of this step's progress slice
                self.progress_updated.emit(step_base + step_range)
                self.log_received.emit(
                    f"<font color='green'><b>[SUCCESS]: Step {step.step_num} completed "
                    f"in {result.elapsed_time_seconds:.2f}s.</b></font>"
                )
                self.step_completed.emit(step.step_num)

            # Finalise
            if success:
                self.progress_updated.emit(100)
                logger.info("Background conversion pipeline executed successfully.")
                self.conversion_completed.emit(True)
            else:
                logger.info("Background conversion pipeline halted due to failure or cancellation.")
                self.conversion_completed.emit(False)

        except Exception as e:
            err_msg = f"Unexpected thread exception inside ConversionWorker: {e}"
            logger.critical(err_msg, exc_info=True)
            self.log_received.emit(
                f"<font color='red'><b>[CRITICAL EXCEPTION]: {err_msg}</b></font>"
            )
            self.conversion_failed.emit(err_msg)
            self.conversion_completed.emit(False)

        finally:
            # Always clean up intermediate scratch files, even on failure
            self._cleanup_intermediates()

    def cancel(self):
        """Thread-safe cancellation request. Safe to call from any thread."""
        logger.warning("Worker cancellation requested.")
        self.cancel_event.set()

    def _cleanup_intermediates(self):
        """Removes temporary intermediate files generated during multi-step pipeline execution."""
        logger.info("Running post-conversion intermediate file cleanup...")
        for step in self.plan.steps:
            if step.is_intermediate and step.output_file:
                try:
                    if os.path.exists(step.output_file):
                        os.remove(step.output_file)
                        logger.info(f"Removed intermediate file: {step.output_file}")
                        self.log_received.emit(
                            f"<font color='#64748b'>[CLEANUP]: Removed intermediate: "
                            f"{step.output_file}</font>"
                        )
                except OSError as e:
                    logger.warning(
                        f"Could not remove intermediate file {step.output_file}: {e}"
                    )
