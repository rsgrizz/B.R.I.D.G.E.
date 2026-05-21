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
        if getattr(sys, 'frozen', False):
            # In PyInstaller, sys.executable points to the packaged executable (e.g. dist/BRIDGE/BRIDGE.exe).
            # The parent of sys.executable is the clean distribution root folder (dist/BRIDGE/).
            return Path(sys.executable).resolve().parent
        # Standard local development run
        return Path(__file__).resolve().parent.parent.parent

    @classmethod
    def get_assets_dir(cls) -> Path:
        """Get the directory containing bundled application image/icon assets."""
        candidates = [cls.get_app_root() / "app" / "assets"]
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            candidates.append(Path(sys._MEIPASS) / "app" / "assets")

        for path in candidates:
            if path.exists():
                return path

        return candidates[0]

    @classmethod
    def get_asset_path(cls, filename: str) -> Path:
        """Resolve a named application asset."""
        return cls.get_assets_dir() / filename

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
        return cls.get_logs_dir() / "bridge.log"

    @classmethod
    def safe_windows_path(cls, path_str: str) -> str:
        """Formats and wraps Windows paths safely (handling spaces, quotes)."""
        p = Path(path_str).resolve()
        return str(p)
