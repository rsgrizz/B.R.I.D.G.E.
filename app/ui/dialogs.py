# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.6
# Date: 5/20/2026
# Purpose: Helper constructors for application-wide warning and info dialog boxes.

import logging
from PySide6.QtWidgets import QMessageBox, QWidget

logger = logging.getLogger(__name__)

class DialogHelper:
    """Helper service containing static dialog constructors for rapid alerts and confirmations."""

    @staticmethod
    def show_overwrite_warning(parent: QWidget, filepath: str) -> bool:
        """Displays an alert warning the user that a target file already exists.
        Returns True if the user elects to overwrite, False to cancel.
        """
        logger.info(f"Triggering overwrite confirmation dialog for: {filepath}")
        reply = QMessageBox.question(
            parent,
            "Overwrite Confirmation",
            f"The destination file already exists:\n\n{filepath}\n\nDo you want to overwrite it?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes

    @staticmethod
    def show_space_warning(parent: QWidget, required_gb: float, available_gb: float) -> bool:
        """Displays a warning dialog about potentially insufficient disk space on the target partition."""
        logger.warning(f"Triggering space warning dialog. Required: {required_gb:.2f}GB, Available: {available_gb:.2f}GB")
        reply = QMessageBox.question(
            parent,
            "Disk Space Warning",
            f"Warning: Low disk space detected on the destination drive.\n\n"
            f"Estimated space required: {required_gb:.2f} GB\n"
            f"Available space: {available_gb:.2f} GB\n\n"
            f"Do you wish to bypass this warning and proceed anyway?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes

    @staticmethod
    def show_critical_error(parent: QWidget, title: str, message: str):
        """Displays a modal warning window for critical operations or execution failures."""
        logger.error(f"Displaying critical error message modal: {title} - {message}")
        QMessageBox.critical(parent, title, message)
