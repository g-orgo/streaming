from collections.abc import Callable


class Lifecycle:
    def __init__(self) -> None:
        self._startups: list[Callable[[], None]] = []
        self._shutdowns: list[Callable[[], None]] = []

    def on_start(self, fn: Callable[[], None]) -> None:
        self._startups.append(fn)

    def on_shutdown(self, fn: Callable[[], None]) -> None:
        self._shutdowns.insert(0, fn)

    def start(self) -> None:
        errors: list[Exception] = []
        for fn in self._startups:
            try:
                fn()
            except Exception as e:
                errors.append(e)
        if errors:
            self.shutdown()
            raise RuntimeError(f"startup falhou: {errors}")

    def shutdown(self) -> None:
        for fn in self._shutdowns:
            try:
                fn()
            except Exception:
                pass
