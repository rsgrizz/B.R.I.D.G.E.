# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.1
# Date: 5/20/2026
# Purpose: Core logger framework configuration for concurrent terminal and file log output.

import logging
import sys
from app.utils.paths import AppPaths

def setup_logging():
    """Initializes standard Python logging.
    Routes log records concurrently to the standard output console
    and to a persistent file in the logs directory.
    """
    log_file = AppPaths.get_log_file_path()
    
    # Create logger instance
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers if any (to avoid duplicate logs on double-init)
    if logger.hasHandlers():
        logger.handlers.clear()
        
    # Text formatter for plain text logging
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] (%(name)s:%(funcName)s:%(lineno)d) - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    
    # 2. File Handler
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        logging.info(f"Persistent logging initialized. Writing logs to {log_file}")
    except Exception as e:
        # Fallback if log folder cannot be written to
        sys.stderr.write(f"Warning: Failed to create file log handler: {e}\n")
        
    logging.info("Logging framework setup complete.")
