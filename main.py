# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.4
# Date: 5/19/2026
# Purpose: Main entry point for the Aegis Forensic Image Converter application.

import sys
import logging
from PySide6.QtWidgets import QApplication
from app.utils.logging_config import setup_logging
from app.ui.main_window import MainWindow

# Initialize system trace logging
setup_logging()
logger = logging.getLogger("main")

def main():
    """Main entry point bootstrapping core components, spawning window controls,
    and launching Qt UI event loops.
    """
    logger.info("Initializing Aegis Forensic Converter system lifecycle...")
    
    app = QApplication(sys.argv)
    
    # Configure application metadata
    app.setApplicationName("Aegis Forensic Converter")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Aegis Security")
    
    # Instantiate Main GUI Window
    main_window = MainWindow()
    main_window.show()
    
    logger.info("Main Window presented to examiner. Entering QApplication event loop.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
