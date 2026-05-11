import os
import tempfile
from pathlib import Path

import pytest

from osint_trader.observability.leader import LeaderLock, LeaderLockError


def test_acquire_release_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "lock"
        lock = LeaderLock(path)
        lock.acquire()
        assert path.exists()
        lock.release()
        assert not path.exists()


def test_second_lock_with_live_pid_raises():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "lock"
        first = LeaderLock(path)
        first.acquire()
        try:
            second = LeaderLock(path)
            with pytest.raises(LeaderLockError):
                second.acquire()
        finally:
            first.release()


def test_stale_lock_is_reclaimed():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "lock"
        path.write_text("99999999")  # PID that almost certainly doesn't exist
        # If by coincidence it does, just skip.
        try:
            os.kill(99999999, 0)
            pytest.skip("PID 99999999 happens to exist")
        except (ProcessLookupError, PermissionError):
            pass
        except OSError:
            pass
        lock = LeaderLock(path)
        lock.acquire()
        assert path.exists()
        lock.release()
