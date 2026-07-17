from live_caption_bridge.domain.models import Caption
from tests.fakes import FakeCaptionSink


def test_fake_sink_receives_caption() -> None:
    sink = FakeCaptionSink()
    caption = Caption(
        original="Olá",
        translated="Hello",
        source_lang="pt",
        target_lang="en",
        started_ns=0,
        ended_ns=100,
    )
    sink.publish(caption)
    assert sink.last is caption
