import time
from collections.abc import Callable


class ResourceGovernor:
    def __init__(
        self,
        queue_max: int = 50,
        check_interval_s: float = 2.0,
    ) -> None:
        self._queue_max = queue_max
        self._interval = check_interval_s
        self._last_check = 0.0
        self._fps_reduced = False
        self._callbacks: list[Callable[[str], None]] = []

    def on_degradation(self, cb: Callable[[str], None]) -> None:
        self._callbacks.append(cb)

    def check(self, queue_size: int) -> None:
        now = time.monotonic()
        if now - self._last_check < self._interval:
            return
        self._last_check = now
        if queue_size > self._queue_max and not self._fps_reduced:
            self._fps_reduced = True
            for cb in self._callbacks:
                cb("fps_reduced")

    def reset(self) -> None:
        self._fps_reduced = False
