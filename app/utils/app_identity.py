# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.1
# Date: 5/22/2026
# Purpose: Stable application identity constants and Windows AppUserModelID setup.

import logging
import os

logger = logging.getLogger(__name__)

APP_GUID = "{8F0F83F6-33B4-4B07-9D2A-C6C8AF4F3117}"
APP_USER_MODEL_ID = "RandyGrizzelli.BRIDGE.8F0F83F6-33B4-4B07-9D2A-C6C8AF4F3117"
APP_ORGANIZATION_NAME = "Randy Grizzelli"
APP_ORGANIZATION_DOMAIN = "github.com/rsgrizz"
APP_DISPLAY_NAME = "B.R.I.D.G.E."
APP_VERSION = "1.0.0"


def apply_windows_app_user_model_id() -> None:
    """Apply the fixed Windows AppUserModelID used for taskbar grouping/icons."""
    if os.name != "nt":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID
        )
    except Exception as exc:
        logger.warning("Unable to set Windows AppUserModelID: %s", exc)
