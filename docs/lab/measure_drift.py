import time
from live_caption_bridge.adapters.ffmpeg_recorder import ffprobe_streams

path = "replay.mp4"
streams = ffprobe_streams(path)
for s in streams:
    print(
        f"  #{s['index']} {s.get('codec_type')} "
        f"codec={s.get('codec_name')} "
        f"title={s.get('tags', {}).get('title', '')} "
        f"dur={s.get('duration')}s"
    )

# Drift: toque 30s e meça diferença PTS vs relógio
t0 = time.monotonic()
# (reprodução real ou leitura de PTS com ffprobe)
print("Meça drift comparando PTS final com duração esperada")
