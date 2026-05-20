# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.3
# Date: 5/20/2026
# Purpose: Memory-safe chunked cryptographic hash computation (MD5, SHA1, SHA256).

import logging
import hashlib
import time
from threading import Event
from typing import Callable
from pathlib import Path
from app.core.models import HashResult

logger = logging.getLogger(__name__)


class HashService:
    """Computes cryptographic integrity checksums (MD5, SHA-1, SHA-256) in a single
    streaming pass over the file, using 64 KB chunks to bound memory usage regardless
    of file size. Supports real-time progress reporting and mid-stream cancellation.
    """

    # Block size for each read() call — 64 KB is a good balance between
    # syscall overhead and memory pressure on large forensic images.
    CHUNK_SIZE: int = 65_536

    @staticmethod
    def calculate_hashes(
        filepath: str,
        progress_callback: Callable[[int], None],
        cancel_event: Event,
    ) -> HashResult:
        """Reads *filepath* in CHUNK_SIZE blocks and feeds every block into
        MD5, SHA-1, and SHA-256 engines simultaneously.

        Progress (0-100) is emitted via *progress_callback* after each chunk.
        If *cancel_event* is set the method returns immediately with
        ``success=False`` and the partial elapsed time recorded.

        Returns a :class:`HashResult`.  On any I/O or unexpected error the
        result has ``success=False`` and a populated ``error_message``.
        """
        logger.info(f"Starting chunked sequential hash computation on: {filepath}")
        start_time = time.monotonic()

        path = Path(filepath)
        if not path.exists() or not path.is_file():
            error_msg = f"File not found or is not a regular file: {filepath}"
            logger.error(error_msg)
            return HashResult("", "", "", 0.0, False, error_msg)

        try:
            total_bytes = path.stat().st_size

            # Initialise all three hashlib context engines
            md5_engine = hashlib.md5(usedforsecurity=False)
            sha1_engine = hashlib.sha1(usedforsecurity=False)
            sha256_engine = hashlib.sha256()

            read_bytes = 0

            with open(path, "rb") as f:
                while True:
                    # Poll cancellation before every read — keeps latency low on
                    # large files without needing a secondary thread.
                    if cancel_event.is_set():
                        elapsed = time.monotonic() - start_time
                        logger.warning(
                            f"Hashing operation cancelled after {elapsed:.2f}s "
                            f"({read_bytes}/{total_bytes} bytes read)."
                        )
                        return HashResult(
                            "", "", "", elapsed, False,
                            "Hashing operation aborted by examiner."
                        )

                    chunk = f.read(HashService.CHUNK_SIZE)
                    if not chunk:
                        break   # Clean EOF

                    md5_engine.update(chunk)
                    sha1_engine.update(chunk)
                    sha256_engine.update(chunk)
                    read_bytes += len(chunk)

                    # Emit progress; guard against division-by-zero on empty files.
                    if total_bytes > 0:
                        progress = int((read_bytes / total_bytes) * 100)
                        # Clamp to [0, 99] — 100 is emitted once after the loop completes
                        progress_callback(min(progress, 99))

            elapsed = time.monotonic() - start_time

            # Final 100% tick — always emitted regardless of file size (including 0-byte)
            progress_callback(100)

            result = HashResult(
                md5=md5_engine.hexdigest(),
                sha1=sha1_engine.hexdigest(),
                sha256=sha256_engine.hexdigest(),
                elapsed_time=elapsed,
                success=True,
            )

            logger.info(
                f"Hashing completed in {elapsed:.3f}s  |  "
                f"MD5: {result.md5}  |  SHA-256: {result.sha256}"
            )
            return result

        except PermissionError as e:
            elapsed = time.monotonic() - start_time
            error_msg = f"Permission denied reading file: {filepath}"
            logger.error(error_msg)
            return HashResult("", "", "", elapsed, False, error_msg)

        except OSError as e:
            elapsed = time.monotonic() - start_time
            error_msg = f"I/O error while hashing {filepath}: {e}"
            logger.error(error_msg)
            return HashResult("", "", "", elapsed, False, error_msg)

        except Exception as e:
            elapsed = time.monotonic() - start_time
            error_msg = f"Unexpected hashing error: {e}"
            logger.error(error_msg, exc_info=True)
            return HashResult("", "", "", elapsed, False, error_msg)
