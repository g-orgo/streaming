from typing import Protocol

from live_caption_bridge.domain.models import Caption


class CaptionSink(Protocol):
    def publish(self, caption: Caption) -> None: ...
