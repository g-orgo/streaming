import os
import tempfile
import threading
from pathlib import Path
from collections.abc import Callable
import subprocess
import shutil


class ReplayService:
    def __init__(
        self,
        max_duration_s: int = 120,
        segment_duration_s: int = 2,
        temp_dir: str | Path | None = None,
    ) -> None:
        self._max_segments = max_duration_s // segment_duration_s
        self._seg_dur = segment_duration_s
        self._temp_dir = Path(temp_dir or tempfile.gettempdir()) / "lcb_replay"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def save_window(
        self,
        segments: list[Path],
        output: str | Path,
        encode_fn: Callable[[list[Path], str | Path], None],
    ) -> None:
        with self._lock:
            encode_fn(segments, output)

    def prune(self, segments: list[Path]) -> list[Path]:
        with self._lock:
            while len(segments) > self._max_segments:
                old = segments.pop(0)
                if old.exists():
                    os.remove(old)
            return segments
    
    def concat_segments(
        self,
        segment_paths: list[Path],
        output: str | Path,
    ) -> None:
        tmp = Path(str(output) + ".tmp.mp4")
        list_path = Path(str(output) + ".list.txt")
        try:
            with open(list_path, "w") as f:
                for seg in segment_paths:
                    f.write(f"file '{seg.resolve()}'\n")
            subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(segment_paths[0])],
                capture_output=True, text=True,
            )
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_path),
                "-c", "copy", str(tmp)],
                check=True, capture_output=True,
            )
            shutil.move(str(tmp), str(output))
        finally:
            if tmp.exists():
                tmp.unlink()
            if list_path.exists():
                list_path.unlink()

