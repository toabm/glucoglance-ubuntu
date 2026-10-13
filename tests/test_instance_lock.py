"""Tests for instance_lock's single-instance flock.

`flock()` locks belong to an open file description, not a process, so two
separate opens of the same file conflict even within one process - which
lets these tests play both the running copy and the second launch.
"""

import subprocess
import sys

from glucoglance import instance_lock


def test_first_acquire_succeeds(tmp_path):
    lock = instance_lock.acquire_instance_lock(tmp_path / "test.lock")
    assert lock is not None
    lock.release()


def test_second_acquire_fails_while_first_is_held(tmp_path):
    path = tmp_path / "test.lock"
    first = instance_lock.acquire_instance_lock(path)
    assert instance_lock.acquire_instance_lock(path) is None
    first.release()


def test_acquire_succeeds_again_after_release(tmp_path):
    path = tmp_path / "test.lock"
    instance_lock.acquire_instance_lock(path).release()
    lock = instance_lock.acquire_instance_lock(path)
    assert lock is not None
    lock.release()


def test_release_twice_does_not_raise(tmp_path):
    lock = instance_lock.acquire_instance_lock(tmp_path / "test.lock")
    lock.release()
    lock.release()


def test_lock_is_released_when_the_holding_process_exits(tmp_path):
    # A crashed or killed copy must never leave a lock behind.
    path = tmp_path / "test.lock"
    holder = (
        "import sys; from pathlib import Path; from glucoglance import instance_lock; "
        "assert instance_lock.acquire_instance_lock(Path(sys.argv[1])) is not None"
    )
    subprocess.run([sys.executable, "-c", holder, str(path)], check=True)
    lock = instance_lock.acquire_instance_lock(path)
    assert lock is not None
    lock.release()


def test_lock_is_not_inherited_by_an_exec(tmp_path):
    # "Restart" / "Log out" re-exec the process; the new image must be able
    # to take the lock, so the descriptor must not survive the exec.
    path = tmp_path / "test.lock"
    child = (
        "import os, sys; from pathlib import Path; from glucoglance import instance_lock; "
        "lock = instance_lock.acquire_instance_lock(Path(sys.argv[1])); "
        "os.execv(sys.executable, [sys.executable, '-c', "
        "'import sys; from pathlib import Path; from glucoglance import instance_lock; "
        "sys.exit(0 if instance_lock.acquire_instance_lock(Path(sys.argv[1])) else 1)', "
        "sys.argv[1]])"
    )
    result = subprocess.run([sys.executable, "-c", child, str(path)])
    assert result.returncode == 0


def test_default_path_is_in_the_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert instance_lock.default_lock_path() == tmp_path / "glucoglance.lock"


def test_default_path_falls_back_to_a_per_user_temp_file(monkeypatch):
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    path = instance_lock.default_lock_path()
    assert path.name.startswith("glucoglance-") and path.suffix == ".lock"
