from typing import Protocol

class ScreenFrame:
    def __init__(self, rgba: bytes, width: int, height: int, pts_ns: int) -> None:
        self.rgba = rgba
        self.width = width
        self.height = height
        self.pts_ns = pts_ns

class RecorderPort(Protocol):
    def capture_frame(self) -> ScreenFrame: ...
    def close(self) -> None: ...
