import logging

LOGGER = logging.getLogger(__name__)

def main() -> int:
    logging.basicConfig(level=logging.INFO)
    LOGGER.info("LiveCaptionBridge iniciado")
    return 0
