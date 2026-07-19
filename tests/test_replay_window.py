from pathlib import Path

from live_caption_bridge.services.replay_service import RingWindow


def test_ring_window_preserves_gaps() -> None:
    w = RingWindow(
        video_segments=[Path("vid1.mp4"), Path("vid2.mp4")],
        mic_segments=[Path("mic1.mp4")],
        sys_segments=[],
        start_ns=0,
        end_ns=4_000_000_000,
    )
    assert len(w.video_segments) == 2
    assert len(w.mic_segments) == 1
    assert len(w.sys_segments) == 0
    assert w.end_ns - w.start_ns == 4_000_000_000
