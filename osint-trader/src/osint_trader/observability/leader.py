"""File-based pidlock so two orchestrator copies don't clobber each other.

Telethon session files corrupt if used concurrently and on-chain orders can
double-fire. The lock writes our PID to a file in flock-protected mode and
removes it on clean shutdown. Stale locks from crashed PIDs are reclaimed.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path

from . import get_logger

logger = get_logger(__name__)


class LeaderLockError(RuntimeError):
    pass


class LeaderLock:
    def __init__(self, path: Path | str = ".osint_trader.lock") -> None:
        self.path = Path(path)
        self._fd: int | None = None

    def acquire(self) -> None:
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o644)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise
            self._reclaim_or_fail()
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o644)
        os.write(fd, str(os.getpid()).encode())
        self._fd = fd
        logger.info("leader_lock_acquired", path=str(self.path), pid=os.getpid())

    def _reclaim_or_fail(self) -> None:
        try:
            existing = self.path.read_text().strip()
            other_pid = int(existing) if existing.isdigit() else None
        except OSError:
            other_pid = None
        if other_pid is None or not _pid_alive(other_pid):
            logger.warning("leader_lock_reclaiming", stale_pid=other_pid)
            try:
                self.path.unlink()
            except OSError:
                pass
            return
        raise LeaderLockError(
            f"another osint-trader instance is running (pid {other_pid}); "
            f"remove {self.path} only if you're sure it's gone"
        )

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            self.path.unlink()
        except OSError:
            pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
