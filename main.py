# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.4
# Date: 5/19/2026
# Purpose: Main entry point for the B.R.I.D.G.E. application.

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
    logger.info("Initializing B.R.I.D.G.E. system lifecycle...")
    
    app = QApplication(sys.argv)
    
    # Configure application metadata
    app.setApplicationName("B.R.I.D.G.E.")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Randy Grizzelli")
    
    # Instantiate Main GUI Window
    main_window = MainWindow()
    main_window.show()
    
    logger.info("Main Window presented to examiner. Entering QApplication event loop.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
