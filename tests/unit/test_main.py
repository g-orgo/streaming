import logging

from live_caption_bridge.main import main

def test_main_inicia_com_sucesso(caplog) -> None:
    with caplog.at_level(logging.INFO):
        exit_code = main()

    assert exit_code == 0
    assert "LiveCaptionBridge iniciado" in caplog.text