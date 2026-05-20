# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.5
# Date: 5/19/2026
# Purpose: Path resolution helpers supporting local environment runs and packaged builds.

import sys
from pathlib import Path

class AppPaths:
    """Utility class to resolve all critical paths for the application,
    supporting both local development and packaged environments (PyInstaller).
    """
    
    @staticmethod
    def get_app_root() -> Path:
        """Get the root directory of the application."""
        # If running as packaged executable
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS)
        # Standard local development run
        return Path(__file__).resolve().parent.parent.parent

    @classmethod
    def get_tools_dir(cls) -> Path:
        """Get the directory where external tool binaries (qemu-img, libewf) reside."""
        # If packaged, tools might be bundled in a specific directory or next to executable
        root = cls.get_app_root()
        # In development, it's a sibling of 'app' directory
        tools_path = root / "tools"
        tools_path.mkdir(exist_ok=True)
        return tools_path

    @classmethod
    def get_logs_dir(cls) -> Path:
        """Get the logs folder, creating it if it doesn't exist."""
        root = cls.get_app_root()
        logs_path = root / "logs"
        logs_path.mkdir(exist_ok=True)
        return logs_path

    @classmethod
    def get_log_file_path(cls) -> Path:
        """Get the file path for the system log file."""
        return cls.get_logs_dir() / "forensic_converter.log"

    @classmethod
    def safe_windows_path(cls, path_str: str) -> str:
        """Formats and wraps Windows paths safely (handling spaces, quotes)."""
        p = Path(path_str).resolve()
        return str(p)
