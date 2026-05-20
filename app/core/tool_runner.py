# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.5
# Date: 5/19/2026
# Purpose: Asynchronous external command line execution wrapper with real-time logging.

import logging
import subprocess
import time
import shutil
import threading
import queue
import os
from threading import Event
from typing import Callable, List
from app.core.models import ToolExecutionResult
from app.utils.paths import AppPaths

logger = logging.getLogger(__name__)

class ToolRunner:
    """Invokes system CLI utilities asynchronously, providing real-time log capturing
    and thread-safe subprocess execution cancellation.
    """

    @staticmethod
    def run_command(cmd: List[str], log_callback: Callable[[str], None], cancel_event: Event) -> ToolExecutionResult:
        """Executes a command list inside a background subprocess.
        Periodically intercepts output streams and monitors cancellation flags.
        """
        if not cmd:
            logger.error("Empty command list passed to ToolRunner.")
            return ToolExecutionResult(
                exit_code=-1, stdout="", stderr="Empty command list", elapsed_time_seconds=0.0, success=False
            )

        start_time = time.time()
        
        # Check for immediate cancellation before invocation
        if cancel_event.is_set():
            logger.info("Subprocess run cancelled before start.")
            return ToolExecutionResult(
                exit_code=-1, stdout="", stderr="", elapsed_time_seconds=0.0, success=False, cancelled=True
            )

        tool_name = cmd[0]
        tools_dir = AppPaths.get_tools_dir()
        
        # Resolve tool path: check local tools folder first
        candidates = [tool_name]
        if os.name == 'nt' and not tool_name.lower().endswith(".exe"):
            candidates.append(f"{tool_name}.exe")
            
        resolved_path = None
        for cand in candidates:
            local_path = tools_dir / cand
            if local_path.is_file():
                resolved_path = str(local_path)
                break
                
        # If not found locally, search host system PATH
        if not resolved_path:
            resolved_path = shutil.which(tool_name)
            if not resolved_path and os.name == 'nt':
                for cand in candidates:
                    res = shutil.which(cand)
                    if res:
                        resolved_path = res
                        break

        # Fall back to command raw executable if both failed (let system try to invoke it)
        if not resolved_path:
            logger.warning(f"Could not resolve tool path for: {tool_name} locally or in PATH. Using raw command token.")
            resolved_path = tool_name

        # Construct final resolved command list
        resolved_cmd = [resolved_path] + cmd[1:]
        logger.info(f"Preparing to run subprocess: {' '.join(resolved_cmd)}")
        
        stdout_accumulator = []
        stderr_accumulator = []
        out_queue = queue.Queue()

        # Thread targets to read pipes concurrently (deadlock protection)
        def reader_thread(stream, queue_obj, label):
            try:
                for line in iter(stream.readline, ''):
                    queue_obj.put((label, line))
            except Exception as e:
                queue_obj.put(('error', str(e)))
            finally:
                stream.close()

        try:
            # Set creation flags on Windows to hide cmd window popup
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW

            # Launch command securely
            process = subprocess.Popen(
                resolved_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                shell=False,
                creationflags=creationflags
            )
            
            # Start stream reader threads
            t_stdout = threading.Thread(target=reader_thread, args=(process.stdout, out_queue, 'stdout'), daemon=True)
            t_stderr = threading.Thread(target=reader_thread, args=(process.stderr, out_queue, 'stderr'), daemon=True)
            t_stdout.start()
            t_stderr.start()

            # Dynamic stream draining and cancellation polling loop
            cancelled = False
            while True:
                # Check for mid-execution cancellation request
                if cancel_event.is_set():
                    logger.warning("Cancellation signal intercepted. Terminating subprocess.")
                    process.terminate()
                    # Wait up to 2 seconds for clean exit, otherwise force kill
                    try:
                        process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        logger.warning("Process did not terminate cleanly. Force killing.")
                        process.kill()
                        process.wait()
                    cancelled = True
                    break

                # Non-blocking read from stdout/stderr queue
                try:
                    label, line = out_queue.get(timeout=0.05)
                    stripped_line = line.rstrip('\r\n')
                    if label == 'stdout':
                        stdout_accumulator.append(line)
                        log_callback(stripped_line)
                    elif label == 'stderr':
                        stderr_accumulator.append(line)
                        log_callback(f"[STDERR]: {stripped_line}")
                    elif label == 'error':
                        logger.error(f"Pipe reader encountered error: {line}")
                except queue.Empty:
                    # Check if subprocess terminated
                    if process.poll() is not None:
                        # Wait for reader threads to finish reading any trailing data
                        t_stdout.join(timeout=0.5)
                        t_stderr.join(timeout=0.5)
                        # Drain remaining items from queue
                        while not out_queue.empty():
                            try:
                                label, line = out_queue.get_nowait()
                                stripped_line = line.rstrip('\r\n')
                                if label == 'stdout':
                                    stdout_accumulator.append(line)
                                    log_callback(stripped_line)
                                elif label == 'stderr':
                                    stderr_accumulator.append(line)
                                    log_callback(f"[STDERR]: {stripped_line}")
                            except queue.Empty:
                                break
                        break

            elapsed = time.time() - start_time
            
            if cancelled:
                logger.info(f"Subprocess cancelled. Elapsed: {elapsed:.2f}s")
                return ToolExecutionResult(
                    exit_code=-9,
                    stdout="".join(stdout_accumulator),
                    stderr="".join(stderr_accumulator) + "\nProcess terminated by examiner.",
                    elapsed_time_seconds=elapsed,
                    success=False,
                    cancelled=True
                )

            exit_code = process.returncode
            success = (exit_code == 0)
            logger.info(f"Subprocess finished with exit code {exit_code}. Success: {success}. Elapsed: {elapsed:.2f}s")

            return ToolExecutionResult(
                exit_code=exit_code,
                stdout="".join(stdout_accumulator),
                stderr="".join(stderr_accumulator),
                elapsed_time_seconds=elapsed,
                success=success,
                cancelled=False
            )
            
        except FileNotFoundError as e:
            elapsed = time.time() - start_time
            error_msg = f"External tool binary not found or inaccessible: {resolved_cmd[0]}"
            logger.error(error_msg)
            log_callback(f"[ERROR]: {error_msg}")
            return ToolExecutionResult(
                exit_code=127, stdout="", stderr=str(e), elapsed_time_seconds=elapsed, success=False
            )
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Unexpected error running command: {e}")
            log_callback(f"[CRITICAL EXCEPTION]: {e}")
            return ToolExecutionResult(
                exit_code=-1, stdout="", stderr=str(e), elapsed_time_seconds=elapsed, success=False
            )
