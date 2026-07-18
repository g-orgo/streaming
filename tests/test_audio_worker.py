import queue
import threading


def test_producer_delivers_three_blocks() -> None:
    q: queue.Queue = queue.Queue(maxsize=10) # type: ignore
    stop = threading.Event()
    blocks = []

    def producer() -> None:
        for _ in range(3):
            if stop.is_set():
                break
            q.put(b"block") # type: ignore
        stop.set()

    t = threading.Thread(target=producer)
    t.start()
    t.join()

    while not q.empty():
        blocks.append(q.get_nowait()) # type: ignore

    assert len(blocks) == 3 # type: ignore
    assert all(b == b"block" for b in blocks) # type: ignore
    assert stop.is_set()