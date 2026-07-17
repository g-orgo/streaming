import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from live_caption_bridge.domain.models import Caption

class Overlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowFlags( # type: ignore
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._label = QLabel("Teste de legenda")
        self._label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)

    def text(self) -> str:
        return self._label.text()

    def display_caption(self, caption: Caption) -> None:
        self._label.setText(
            caption.translated or caption.original
        )


def main() -> None:
    app = QApplication(sys.argv)
    overlay = Overlay()
    overlay.show()
    caption = Caption(
        original="Olá mundo",
        translated="Hello world",
        source_lang="pt",
        target_lang="en",
        started_ns=0,
        ended_ns=100,
    )
    overlay.display_caption(caption)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()