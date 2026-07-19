import mss
from live_caption_bridge.adapters.ffmpeg_recorder import encode_segment

with mss.MSS() as sct:
    monitor = sct.monitors[1]
    info = sct.grab(monitor)
    frames = [bytes(sct.grab(monitor).raw) for _ in range(30)]

encode_segment(frames, info.width, info.height, "segment.mp4", fps=15)
