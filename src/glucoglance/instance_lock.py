"""Keeps GlucoGlance to one running copy per user.

Starting the app while it's already running (e.g. from the Applications
menu, or by typing `glucoglance` again) would otherwise put a second,
identical icon in the top bar and poll LibreLinkUp twice. `main()` takes
this lock before doing anything else, and gives up if another copy holds
it.

It's an `flock()` on a file in `$XDG_RUNTIME_DIR` (the per-user runtime
directory, `/run/user/<uid>`), rather than a PID file, because the kernel
releases it by itself whenever the holder's file descriptor goes away:
- when the app exits, crashes or is killed, so a stale lock can never
  block the next start;
- on the tray's "Restart" / "Log out", which re-exec the process with
  `os.execv`: Python opens files as non-inheritable (PEP 446), so the
  descriptor is closed across the exec and the fresh process can take the
  lock again.
"""

import fcntl
import os
import tempfile
from pathlib import Path

_LOCK_FILE_NAME = "glucoglance.lock"


class InstanceLock:
    """Holds the single-instance lock until `release()` is called or the
    process ends. Keep a reference to it for as long as the app runs."""

    def __init__(self, fd: int):
        self._fd: int | None = fd

    def release(self) -> None:
        """Release the lock now (closing the descriptor drops the flock)."""
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


def default_lock_path() -> Path:
    """The lock file's location: the per-user runtime directory, or the
    temp directory (with the user id in the name) if that isn't set."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / _LOCK_FILE_NAME
    return Path(tempfile.gettempdir()) / f"glucoglance-{os.getuid()}.lock"


def acquire_instance_lock(path: Path | None = None) -> InstanceLock | None:
    """Take the single-instance lock, or return None if another running
    copy already holds it."""
    fd = os.open(path or default_lock_path(), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    # Only for whoever inspects the file by hand; nothing reads it back.
    os.ftruncate(fd, 0)
    os.write(fd, f"{os.getpid()}\n".encode())
    return InstanceLock(fd)
