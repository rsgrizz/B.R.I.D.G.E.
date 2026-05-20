# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.4
# Date: 5/19/2026
# Purpose: Cryptographic hash extraction process running as a background runnable worker.

import logging
from threading import Event
from PySide6.QtCore import QRunnable, QObject, Signal
from app.core.models import HashResult
from app.core.hash_service import HashService

logger = logging.getLogger(__name__)

class HashWorkerSignals(QObject):
    """Custom signals helper object for QRunnable, since QRunnable itself is not a QObject."""
    hash_progress = Signal(int)             # Percent (0-100)
    hash_completed = Signal(object)         # HashResult
    hash_failed = Signal(str)               # Error message string

class HashWorker(QRunnable):
    """Memory-safe file integrity checksum calculator running on the global QThreadPool."""
    
    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath
        self.signals = HashWorkerSignals()
        self.cancel_event = Event()

    def run(self):
        """Asynchronous execution slot inside the thread pool."""
        logger.info(f"Background HashWorker triggered for file: {self.filepath}")
        
        def local_progress_cb(percent: int):
            self.signals.hash_progress.emit(percent)
            
        try:
            result = HashService.calculate_hashes(
                self.filepath,
                local_progress_cb,
                self.cancel_event
            )
            
            if result.success:
                self.signals.hash_completed.emit(result)
            else:
                self.signals.hash_failed.emit(result.error_message or "Unknown hashing error.")
                
        except Exception as e:
            err_msg = f"Unexpected exception in HashWorker task: {e}"
            logger.error(err_msg, exc_info=True)
            self.signals.hash_failed.emit(err_msg)

    def cancel(self):
        """Signals background hash calculations to abort instantly."""
        logger.warning("Hash task cancellation requested.")
        self.cancel_event.set()
