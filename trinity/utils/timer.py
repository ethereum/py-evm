import time


class Timer:
    _start: float = None

    def __init__(self, auto_start: bool = True) -> None:
        if auto_start:
            self.start()

    def start(self) -> None:
        self._start = time.perf_counter()

    def pop_elapsed(self) -> float:
        """Return time elapsed since last start, and start the timer over"""
        now = time.perf_counter()
        elapsed = now - self._start
        self._start = now
        return elapsed

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self._start
