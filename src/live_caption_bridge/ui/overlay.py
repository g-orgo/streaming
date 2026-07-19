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
        self.setStyleSheet("""
            Overlay { background-color: rgba(0, 0, 0, 160); border-radius: 8px; }
            QLabel { color: white; font-size: 26px; font-weight: bold; padding: 6px 16px; }
        """)
        self._label = QLabel("Teste de legenda")
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self._position_at_bottom()

    def _position_at_bottom(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            width = int(geo.width() * 0.6)
            x = (geo.width() - width) // 2
            y = geo.height() - 80
            self.setGeometry(x, y, width, 60)

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