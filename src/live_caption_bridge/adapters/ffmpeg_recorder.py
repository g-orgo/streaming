import subprocess
from pathlib import Path
from typing import Any

import mss


def capture_one_frame() -> dict[str, Any]:
    with mss.MSS() as sct: # type: ignore
        monitor = sct.monitors[1] # type: ignore
        frame = sct.grab(monitor) # type: ignore
        return {
            "width": frame.width, # type: ignore
            "height": frame.height, # type: ignore
            "pixel_format": "BGRA",
            "monitor": monitor,
        }

def _ffmpeg_encode(
    frames: list[bytes],
    width: int,
    height: int,
    output_path: str | Path,
    fps: int = 15,
) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "bgra",
        "-r", str(fps),
        "-i", "-",
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        str(output_path),
    ]
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if proc.stdin:
        for frame in frames:
            proc.stdin.write(frame)
        proc.stdin.close()
    proc.wait()


def encode_segment(
    frames: list[bytes], width: int, height: int, output: str | Path, fps: int = 15
) -> None:
    _ffmpeg_encode(frames, width, height, output, fps)
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
         str(output)],
        capture_output=True, text=True,
    )
    duration = result.stdout.strip()
    print(f"Segmento salvo: {output}, duração: {duration}s")



if __name__ == "__main__":
    info = capture_one_frame()
    print(f"Monitor: {info['monitor']}")
    print(f"Tamanho: {info['width']}x{info['height']}, Formato: {info['pixel_format']}")
