import time


class Timer:
    _start: float = None

    def __init__(self, auto_start: bool = True) -> None:
        if auto_start:
            self.start()

    def start(self) -> None:
        self._start = time.perf_counter()

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self._start
