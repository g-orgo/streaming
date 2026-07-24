import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from PyStreamingTool.ui.local_server import port

"""
    Enxergue isto como se estivéssemos falando de um caminho windows;
    Por exemplo "C:/" estamos definindo que:
    De onde parte este arquivo, porém, estamos falando sobre o caminho "parente" (ou seja,
    aquele que vem antes, src/PyStreamingTool/ui)/views.
    Isso fica dessa maneira (src/PyStreamingTool/ui/views)
"""
VIEWS_DIR = Path(__file__).parent / "views"
CORE_DIR = Path(__file__).parent / "core"


class MainWindow(QMainWindow):
    """Geração de aplicativo windows"""

    def __init__(self):
        """Definição de parâmetros"""
        super().__init__()
        self.setWindowTitle("StreamingTool")  # "Nome" do aplicativo para o OS
        self.resize(1024, 768)  # Tamanho inicial do aplicativo

        container = QWidget()  # Criação do primeiro container de widget
        self.setCentralWidget(
            # Centralizar widget no windows horizontalmente
            container
        )
        layout = QVBoxLayout(container)  # Centralizar widget no windows verticalmente

        self.browser = QWebEngineView()  # Criação da aplicação em si, o corpo dela
        layout.addWidget(self.browser)  # Adicionando ao layout o widget criado

        self.browser.setUrl(
            # Define a url inicial do projeto
            QUrl(f"http://127.0.0.1:{port}/core/index.html")
        )


app = QApplication(sys.argv)
if __name__ == "__main__":
    """ 
        Isso impede que ao ser importado rode o aplicativo
        sem congelar. Isso é util para testes por exemplo.
    """
    window = MainWindow()
    shutdown_shortcut = QShortcut(QKeySequence("Ctrl+Q"), window)
    shutdown_shortcut.activated.connect(app.quit)
    window.show()
    sys.exit(app.exec())
