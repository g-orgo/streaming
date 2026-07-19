import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox,  QPushButton, QSpinBox,
    QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from live_caption_bridge.infrastructure.settings import Settings
from live_caption_bridge.ui.overlay import Overlay


class ConfigTab(QWidget):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        layout = QVBoxLayout(self)

        audio_group = QGroupBox("Áudio")
        audio_layout = QFormLayout(audio_group)
        self._mic_combo = QComboBox()
        self._speaker_combo = QComboBox()
        audio_layout.addRow("Microfone:", self._mic_combo)
        audio_layout.addRow("Alto-falante:", self._speaker_combo)
        layout.addWidget(audio_group)

        llm_group = QGroupBox("Tradução (LLM)")
        llm_layout = QFormLayout(llm_group)
        self._llm_url = QLineEdit(settings.llm_url)
        self._llm_model = QLineEdit(settings.llm_model)
        self._source_lang = QComboBox()
        self._source_lang.addItems(["en", "pt", "es", "fr", "de"])
        self._target_lang = QComboBox()
        self._target_lang.addItems(["pt", "en", "es", "fr", "de"])
        self._target_lang.setCurrentText("pt")
        llm_layout.addRow("URL:", self._llm_url)
        llm_layout.addRow("Modelo:", self._llm_model)
        llm_layout.addRow("Idioma origem:", self._source_lang)
        llm_layout.addRow("Idioma destino:", self._target_lang)
        layout.addWidget(llm_group)

        replay_group = QGroupBox("Replay")
        replay_layout = QFormLayout(replay_group)
        self._replay_seconds = QSpinBox()
        self._replay_seconds.setRange(10, 600)
        self._replay_seconds.setValue(settings.replay_seconds)
        replay_layout.addRow("Segundos de replay:", self._replay_seconds)
        layout.addWidget(replay_group)

        layout.addStretch()
        self._status_label = QLabel("Parado")
        layout.addWidget(self._status_label)

    def refresh_devices(self, mics: list[str], speakers: list[str]) -> None:
        self._mic_combo.clear()
        self._mic_combo.addItems(mics)
        self._speaker_combo.clear()
        self._speaker_combo.addItems(speakers)


class VideosTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._list = QListWidget()
        layout.addWidget(QLabel("Vídeos de replay gerados:"))
        layout.addWidget(self._list)
        btn_layout = QHBoxLayout()
        self._refresh_btn = QPushButton("Atualizar")
        self._open_btn = QPushButton("Abrir pasta")
        btn_layout.addWidget(self._refresh_btn)
        btn_layout.addWidget(self._open_btn)
        layout.addLayout(btn_layout)

    def refresh(self, files: list[Path]) -> None:
        self._list.clear()
        for f in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True):
            size = f.stat().st_size / 1024 / 1024
            item = QListWidgetItem(f"{f.name} ({size:.1f} MB)")
            item.setData(Qt.ItemDataRole.UserRole, str(f))
            self._list.addItem(item)


class InstructionsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml("""
        <h2>LiveCaptionBridge</h2>
        <p>Legendas simultâneas e replay de tela com áudio no Windows.</p>
        <h3>Como usar</h3>
        <ol>
          <li>Na aba <b>Config</b>, selecione microfone e alto-falante.</li>
          <li>Configure o servidor LLM (Ollama local ou remoto).</li>
          <li>Clique em <b>Iniciar</b> para começar a captura.</li>
          <li>A legenda aparecerá no overlay transparente.</li>
          <li>Pressione o atalho global para salvar os últimos N segundos.</li>
        </ol>
        <h3>Requisitos</h3>
        <ul>
          <li>Python 3.12+</li>
          <li>FFmpeg no PATH</li>
          <li>Modelo Vosk em %USERPROFILE%\\Vosk\\</li>
          <li>Ollama (ou LLM compatível) para tradução</li>
        </ul>
        <h3>Atalhos</h3>
        <ul>
          <li><b>Ctrl+Shift+S</b> — Salvar replay</li>
          <li><b>Ctrl+Shift+Q</b> — Sair</li>
        </ul>
        """)
        layout.addWidget(browser)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LiveCaptionBridge")
        self.resize(700, 500)

        self._settings = Settings()
        self._overlay = Overlay()
        self._overlay.show()

        tabs = QTabWidget()
        self._config_tab = ConfigTab(self._settings)
        self._videos_tab = VideosTab()
        self._instructions_tab = InstructionsTab()
        tabs.addTab(self._config_tab, "Config")
        tabs.addTab(self._videos_tab, "Vídeos")
        tabs.addTab(self._instructions_tab, "Instruções")
        self.setCentralWidget(tabs)

        self._init_menu()

        self._running = False
        self._timer = QTimer()
        self._timer.timeout.connect(self._on_tick)

    def _init_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("Arquivo")
        quit_action = QAction("Sair", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = menu.addMenu("Ajuda")
        about_action = QAction("Sobre", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self) -> None:
        QMessageBox.about(self, "LiveCaptionBridge",
                          "Versão 0.1.0\n\nLegendas simultâneas e replay recente.")

    def _on_tick(self) -> None:
        pass

    def closeEvent(self, event: QCloseEvent) -> None:
        self._overlay.close()
        event.accept()


def run_ui() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("LiveCaptionBridge")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
