from pytestqt.qtbot import QtBot

from live_caption_bridge.domain.models import Caption


def test_overlay_starts_with_placeholder(qtbot: QtBot) -> None:
    from live_caption_bridge.ui.overlay import Overlay

    overlay = Overlay()
    qtbot.addWidget(overlay)
    assert overlay.text() == "Teste de legenda"

def test_overlay_displays_caption(qtbot: QtBot) -> None:
    from live_caption_bridge.ui.overlay import Overlay


    overlay = Overlay()
    qtbot.addWidget(overlay)
    caption = Caption(
        original="Olá",
        translated="Hello",
        source_lang="pt",
        target_lang="en",
        started_ns=0,
        ended_ns=100,
    )
    overlay.display_caption(caption)
    assert "Hello" in overlay.text()
