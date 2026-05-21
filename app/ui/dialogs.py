# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.10
# Date: 5/21/2026
# Purpose: Helper constructors for application-wide warning and info dialog boxes.

import logging
from PySide6.QtWidgets import QMessageBox, QWidget

logger = logging.getLogger(__name__)


class DialogHelper:
    """Static dialog constructors for rapid alerts and confirmations.

    All methods are synchronous (blocking) — they use ``QMessageBox.exec()``
    internally and return only after the user dismisses the dialog.
    """

    @staticmethod
    def show_overwrite_warning(parent: QWidget, filepath: str) -> bool:
        """Modal dialog asking whether an existing output file should be overwritten.

        Returns ``True`` if the user clicks Yes (overwrite approved),
        ``False`` if the user clicks No (declined — treat as clean cancellation).
        """
        logger.info(f"Overwrite confirmation dialog for: {filepath}")
        box = QMessageBox(parent)
        box.setWindowTitle("Overwrite Confirmation")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("The destination file already exists:")
        box.setInformativeText(
            f"<b>{filepath}</b><br><br>"
            "Do you want to overwrite it? This cannot be undone."
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        result = box.exec()
        approved = result == QMessageBox.StandardButton.Yes
        logger.info(f"Overwrite decision: {'approved' if approved else 'declined'}")
        return approved

    @staticmethod
    def show_space_warning(parent: QWidget, required_gb: float, available_gb: float) -> bool:
        """Modal dialog warning about potentially insufficient disk space.

        Returns ``True`` if the user chooses to proceed anyway,
        ``False`` if the user cancels.
        """
        logger.warning(
            f"Disk space warning dialog — required: {required_gb:.2f} GB, "
            f"available: {available_gb:.2f} GB"
        )
        box = QMessageBox(parent)
        box.setWindowTitle("Disk Space Warning")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("Low disk space detected on the destination drive.")
        box.setInformativeText(
            f"<b>Estimated space required:</b> {required_gb:.2f} GB<br>"
            f"<b>Available space:</b> {available_gb:.2f} GB<br><br>"
            "Proceeding may cause an incomplete or corrupt output file.<br>"
            "Do you wish to continue anyway?"
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        result = box.exec()
        approved = result == QMessageBox.StandardButton.Yes
        logger.info(f"Space warning decision: {'proceed' if approved else 'cancelled'}")
        return approved

    @staticmethod
    def show_validation_errors(parent: QWidget, error_lines: list[str]) -> None:
        """Modal dialog displaying one or more hard validation errors.

        Used when ``ValidationResult.passed`` is ``False`` and the GUI
        needs to surface all ERROR-severity messages at once.
        """
        logger.error(f"Validation error dialog — {len(error_lines)} error(s)")
        box = QMessageBox(parent)
        box.setWindowTitle("Pre-flight Validation Failed")
        box.setIcon(QMessageBox.Icon.Critical)
        box.setText("Conversion cannot proceed due to the following errors:")
        box.setInformativeText("<br>".join(f"• {e}" for e in error_lines))
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    @staticmethod
    def show_critical_error(parent: QWidget, title: str, message: str) -> None:
        """Generic modal for critical runtime failures."""
        logger.error(f"Critical error dialog: {title} — {message}")
        QMessageBox.critical(parent, title, message)

    @staticmethod
    def show_experimental_warning(parent: QWidget) -> bool:
        """Modal confirmation before launching an experimental conversion path.

        Returns ``True`` if the user confirms, ``False`` if they cancel.
        """
        box = QMessageBox(parent)
        box.setWindowTitle("Experimental Conversion Path")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("This conversion path is marked EXPERIMENTAL.")
        box.setInformativeText(
            "It may fail, produce incomplete output, or behave unexpectedly.<br><br>"
            "Do you wish to proceed?"
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes
