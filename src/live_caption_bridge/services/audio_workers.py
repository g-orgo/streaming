import queue
import threading
from collections.abc import Callable

from live_caption_bridge.domain.models import AudioChunk, AudioSource


class AudioWorker:
    def __init__(
        self,
        source: AudioSource,
        read_chunk: Callable[[], AudioChunk],
        maxsize: int = 10,
    ) -> None:
        self._source = source
        self._read = read_chunk
        self._queue: queue.Queue[AudioChunk] = queue.Queue(maxsize=maxsize)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        def _run() -> None:
            while not self._stop.is_set():
                try:
                    chunk = self._read()
                    self._queue.put(chunk, timeout=0.1)
                except queue.Full:
                    continue
                except Exception:
                    if not self._stop.is_set():
                        raise
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def read(self) -> AudioChunk | None:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None
