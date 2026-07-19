import sys
import logging

from live_caption_bridge.ui.main_window import run_ui

LOGGER = logging.getLogger(__name__)

def main() -> int:
    logging.basicConfig(level=logging.INFO)
    LOGGER.info("LiveCaptionBridge iniciado")
    run_ui()
    return 0
