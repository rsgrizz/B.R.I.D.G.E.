# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.4
# Date: 5/19/2026
# Purpose: Main entry point for the B.R.I.D.G.E. application.

import sys
import logging
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from app.utils.app_identity import (
    APP_DISPLAY_NAME,
    APP_GUID,
    APP_ORGANIZATION_DOMAIN,
    APP_ORGANIZATION_NAME,
    APP_USER_MODEL_ID,
    APP_VERSION,
    apply_windows_app_user_model_id,
)
from app.utils.logging_config import setup_logging
from app.utils.paths import AppPaths
from app.ui.main_window import MainWindow

# Initialize system trace logging
setup_logging()
logger = logging.getLogger("main")

def main():
    """Main entry point bootstrapping core components, spawning window controls,
    and launching Qt UI event loops.
    """
    logger.info("Initializing B.R.I.D.G.E. system lifecycle...")
    apply_windows_app_user_model_id()
    
    app = QApplication(sys.argv)
    
    # Configure application metadata
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORGANIZATION_NAME)
    app.setOrganizationDomain(APP_ORGANIZATION_DOMAIN)
    app.setDesktopFileName(APP_USER_MODEL_ID)
    app.setProperty("applicationGuid", APP_GUID)

    icon_path = AppPaths.get_asset_path("bridge.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    # Instantiate Main GUI Window
    main_window = MainWindow()
    main_window.show()
    
    logger.info("Main Window presented to examiner. Entering QApplication event loop.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
