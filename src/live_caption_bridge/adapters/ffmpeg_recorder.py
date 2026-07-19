import subprocess
from pathlib import Path
from typing import Any, cast

import mss


def capture_one_frame() -> dict[str, Any]:
    with mss.MSS() as sct:
        monitor = sct.monitors[1]
        frame = sct.grab(monitor)
        return {
            "width": frame.width,
            "height": frame.height,
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

def mux_video_audio(
    video_path: str | Path,
    audio_path: str | Path | None,
    output: str | Path,
    audio_title: str = "System",
) -> None:
    cmd = ["ffmpeg", "-y", "-i", str(video_path)]
    if audio_path:
        cmd += ["-i", str(audio_path)]
        cmd += ["-c:v", "copy", "-c:a", "aac"]
        cmd += ["-metadata:s:a:0", f"title={audio_title}"]
        cmd += ["-map", "0:v:0", "-map", "1:a:0"]
    else:
        cmd += ["-c:v", "copy"]
    cmd.append(str(output))
    subprocess.run(cmd, check=True, capture_output=True)


def ffprobe_streams(path: str | Path) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    import json
    data: Any = json.loads(result.stdout)
    return cast("list[dict[str, Any]]", data.get("streams", []))

def mux_three_tracks(
    video: str | Path,
    mic_audio: str | Path | None,
    sys_audio: str | Path | None,
    output: str | Path,
) -> None:
    cmd = ["ffmpeg", "-y", "-i", str(video)]
    inputs = [video]
    maps = ["-map", "0:v:0"]
    if mic_audio:
        cmd += ["-i", str(mic_audio)]
        maps += ["-map", f"{len(inputs)}:a:0"]
        inputs.append(mic_audio)
    if sys_audio:
        cmd += ["-i", str(sys_audio)]
        maps += ["-map", f"{len(inputs)}:a:0"]
        inputs.append(sys_audio)
    cmd += ["-c:v", "copy"]
    if mic_audio or sys_audio:
        cmd += ["-c:a", "aac"]
    track_idx = 0
    if mic_audio:
        cmd += ["-metadata:s:a:" + str(track_idx), "title=Mic"]
        track_idx += 1
    if sys_audio:
        cmd += ["-metadata:s:a:" + str(track_idx), "title=System"]
    cmd += maps
    cmd.append(str(output))
    subprocess.run(cmd, check=True, capture_output=True)


if __name__ == "__main__":
    info = capture_one_frame()
    print(f"Monitor: {info['monitor']}")
    print(f"Tamanho: {info['width']}x{info['height']}, Formato: {info['pixel_format']}")
