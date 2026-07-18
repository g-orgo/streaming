import queue
import threading


def test_worker_stops_on_even() -> None:
    q: queue.Queue[bytes] = queue.Queue(maxsize=10)
    stop = threading.Event()

    def worker() -> None:
        while not stop.is_set():
            try:
                q.put(b"dummy", timeout=0.1)
            except queue.Full:
                pass

    t = threading.Thread(target=worker)
    t.start()
    stop.set()
    t.join(timeout=2)

    assert not t.is_alive()
