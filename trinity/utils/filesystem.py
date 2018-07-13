import os
from pathlib import Path


def is_same_path(p1: str, p2: str) -> bool:
    n_p1 = os.path.abspath(os.path.expanduser(p1))
    n_p2 = os.path.abspath(os.path.expanduser(p2))

    try:
        return os.path.samefile(n_p1, n_p2)
    except FileNotFoundError:
        return n_p1 == n_p2


def is_under_path(base_path: str, path: str, strict: bool=True) -> bool:
    if is_same_path(base_path, path):
        if strict:
            return False
        else:
            return True
    absolute_base_path = os.path.abspath(base_path)
    absolute_path = os.path.abspath(path)
    return absolute_path.startswith(absolute_base_path)


class PidFile:
    """
    This class tracks the process id of the currently running process in a file.
    Use it as a context manager so that the file gets cleaned up in a graceful shutdown.
    There are some corner cases that may cause the pidfile to be left behind with a dead process,
    but any running process within the context of a PidFile should always have an
    associated pid file.

    It happens to usually prevent running two processes with the same process_name
    at the same time, but does not guarantee this behavior.
    """
    def __init__(self, process_name: str, path: Path) -> None:
        self.filepath = path / (process_name + '.pid')
        self._running = False

    def __enter__(self) -> None:
        if self.filepath.exists():
            raise FileExistsError(
                "File %s already exists -- cannot run the same process twice" % self.filepath
            )
        elif self._running:
            raise RuntimeError("Cannot enter the same PidFile context twice")
        if not self.filepath.parent.is_dir():
            raise IOError(
                "Cannot create pidfile in base directory that doesn't exist: %s" % self.filepath
            )
        else:
            self._running = True

            # try to create the pidfile, failing if it already exists
            with self.filepath.open('x') as pidfile:
                pidfile.write(str(os.getpid()) + "\n")

    def __exit__(self, exc_type=None, exc_value=None, exc_tb=None):  # type: ignore
        self.filepath.unlink()
        self._running = False
