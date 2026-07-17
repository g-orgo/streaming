from live_caption_bridge.domain.models import Caption

class FakeCaptionSink:
    def __init__(self) -> None:
        self.last: Caption | None = None
    def publish(self, caption: Caption) -> None:
        self.last = caption