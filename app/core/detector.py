# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.4
# Date: 5/19/2026
# Purpose: Forensic image format detection based on binary magic signatures and file extensions.

import logging
import re
from pathlib import Path
from app.core.models import FileFormat, DetectionMethod, DetectionResult

logger = logging.getLogger(__name__)

class FormatDetector:
    """Format Detector to identify input files based on binary signatures
    (magic bytes) and fallback to extension-based heuristics.
    """

    EXTENSION_MAP = {
        ".e01": FileFormat.E01,
        ".ex01": FileFormat.EX01,
        ".dmg": FileFormat.DMG,
        ".dd": FileFormat.RAW,
        ".raw": FileFormat.RAW,
        ".img": FileFormat.RAW,
        ".vmdk": FileFormat.VMDK,
        ".vhd": FileFormat.VHD,
        ".vhdx": FileFormat.VHDX,
        ".qcow2": FileFormat.QCOW2,
    }

    # Exact magic byte headers (offset 0)
    SIGNATURES_HEADER = {
        b"EVF\x09\x0d\x0a\xff\x00": FileFormat.E01,       # E01 / EWF (EnCase physical image / SMART)
        b"EVF2\x0d\x0a\xff\x00": FileFormat.EX01,      # Ex01 / EWF2 (EnCase physical v7)
        b"LVF\x09\x0d\x0a\xff\x00": FileFormat.EX01,      # L01 Logical Evidence File (maps to EX01 family)
        b"QFI\xfb": FileFormat.QCOW2,                  # QCOW2 (4 bytes)
        b"KDMV": FileFormat.VMDK,                      # VMDK (4 bytes)
        b"vhdxfile": FileFormat.VHDX,                  # VHDX (8 bytes)
        b"conectix": FileFormat.VHD,                   # VHD sparse/dynamic header (8 bytes)
    }

    # Compiled patterns for broad E01/EWF family extension detection
    # Classic EWF physical & SMART formats: .e01-.e99, .eaa-.ezz, .s01-.s99, .saa-.szz
    CLASSIC_EWF_RE = re.compile(r"^\.[es](?:[0-9]{2}|[a-z]{2})$")

    # Newer EnCase v7 EX01 & L01 Logical evidence formats: .ex01-.ex99, .exaa-.exzz, .l01-.l99, .laa-.lzz
    EX_EWF_RE = re.compile(r"^\.(?:ex|l)(?:[0-9]{2}|[a-z]{2})$")

    @classmethod
    def detect_format(cls, filepath: str) -> DetectionResult:
        """Determines the forensic or disk image format.
        Tries binary signature mapping first, falling back to extension matching.
        """
        logger.info(f"Initiating binary format detection for file: {filepath}")
        
        path = Path(filepath)
        if not path.exists() or not path.is_file():
            logger.warning(f"File does not exist or is not accessible: {filepath}")
            return DetectionResult(FileFormat.UNKNOWN, DetectionMethod.UNKNOWN, "Low")
            
        file_size = path.stat().st_size
        
        # 1. Attempt magic byte checks from header (first 512 bytes)
        try:
            with open(path, "rb") as f:
                header = f.read(512)
                
            # Direct match at offset 0
            for sig, fmt in cls.SIGNATURES_HEADER.items():
                if header.startswith(sig):
                    logger.info(f"Verified {fmt.value} signature at offset 0.")
                    return DetectionResult(fmt, DetectionMethod.SIGNATURE, "High")
                    
        except Exception as e:
            logger.error(f"Failed to read header sector for signature detection: {e}")

        # 2. Attempt magic checks from trailer (last 512 bytes) for VHD / DMG
        if file_size >= 512:
            try:
                with open(path, "rb") as f:
                    f.seek(file_size - 512)
                    trailer = f.read(512)
                    
                # Apple DMG standard trailer begins with 'koly' signature (offset 0 of last sector)
                if trailer.startswith(b"koly"):
                    logger.info("Verified Apple DMG 'koly' signature in trailer.")
                    return DetectionResult(FileFormat.DMG, DetectionMethod.SIGNATURE, "High")
                    
                # Legacy Microsoft VHD trailer ends or starts with 'conectix' signature
                if trailer.startswith(b"conectix") or trailer.endswith(b"conectix"):
                    logger.info("Verified legacy Microsoft VHD 'conectix' signature in trailer.")
                    return DetectionResult(FileFormat.VHD, DetectionMethod.SIGNATURE, "High")
                    
            except Exception as e:
                logger.error(f"Failed to read trailer sector for signature detection: {e}")

        # 3. Fallback to explicit extension-based heuristics
        ext = path.suffix.lower()
        if ext in cls.EXTENSION_MAP:
            detected_fmt = cls.EXTENSION_MAP[ext]
            logger.info(f"Fallback matched extension {ext} to format {detected_fmt.value}.")
            return DetectionResult(detected_fmt, DetectionMethod.EXTENSION, "Medium")

        # 4. Fallback to pattern-based extension checks for split segments & family formats
        if cls.CLASSIC_EWF_RE.match(ext):
            logger.info(f"Fallback pattern matched classic EWF family segment extension {ext} to E01.")
            return DetectionResult(FileFormat.E01, DetectionMethod.EXTENSION, "Medium")
            
        if cls.EX_EWF_RE.match(ext):
            logger.info(f"Fallback pattern matched newer/logical EWF family segment extension {ext} to EX01.")
            return DetectionResult(FileFormat.EX01, DetectionMethod.EXTENSION, "Medium")

        logger.warning(f"Unable to determine file format for: {path.name}")
        return DetectionResult(FileFormat.UNKNOWN, DetectionMethod.UNKNOWN, "Low")
