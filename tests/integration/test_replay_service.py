import threading
import tempfile
from pathlib import Path
from live_caption_bridge.services.replay_service import ReplayService



def test_prune_removes_excess_segments() -> None:
    svc = ReplayService(max_duration_s=6, segment_duration_s=2)
    import pathlib
    segments = [pathlib.Path(f"seg{i}.mp4") for i in range(5)]
    for s in segments:
        s.write_text("fake")
    try:
        remaining = svc.prune(segments)
        assert len(remaining) <= 3
    finally:
        for s in segments:
            p = pathlib.Path(s)
            if p.exists():
                p.unlink()

def test_concurrent_saves_do_not_collide() -> None:
    svc = ReplayService(max_duration_s=30, segment_duration_s=2)
    results: list[Exception | None] = [None, None]
    threading.Lock()

    def fake_encode(segments: list[Path], out: str | Path) -> None:
        Path(out).write_text("ok")

    def save(idx: int) -> None:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / f"out{idx}.mp4"
                svc.save_window([], out, fake_encode)
        except Exception as e:
            results[idx] = e

    t1 = threading.Thread(target=save, args=(0,))
    t2 = threading.Thread(target=save, args=(1,))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert all(r is None for r in results)
