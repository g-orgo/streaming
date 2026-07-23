from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl
# from PySide6.QtCore import QUrl, QObject, Slot
# from PySide6.QtWebChannel import QWebChannel
from pathlib import Path
import sys

HTML_DIR = (
    Path(__file__).parent / "html"
)  # Isso significa {Path deste arquivo}.parent (ou seja /ui/)/html. Ficando assim: PyStreamingTool/ui/html.


# class Bridge(QObject):
#     @Slot(str)
#     def log_from_js(self, msg: str) -> None:
#         print(f"[JS]: {msg}")

#     @Slot(str, result=str)
#     def ask_python(self, question: str) -> str:
#         return f"Python respondeu: {question}"


class MainWindow(QMainWindow):
    """Geração de aplicativo windows"""

    def __init__(self):
        """Definição de parâmetros"""
        super().__init__()
        self.setWindowTitle("StreamingTool")  # "Nome" do aplicativo para o OS
        self.resize(1024, 768)  # Tamanho inicial do aplicativo

        container = QWidget()  # Criação do primeiro container de widget
        self.setCentralWidget(
            container
        )  # Centralizar widget no windows horizontalmente
        layout = QVBoxLayout(container)  # Centralizar widget no windows verticalmente

        self.browser = QWebEngineView()  # Criação da aplicação em si, o corpo dela
        layout.addWidget(self.browser)  # Adicionando ao layout o widget criado

        # channel = QWebChannel()  # Isso cria a comunicação com o client HTML
        # self.bridge = Bridge()  # A ponte entre o que foi pedido pelo JS e o que será interpretado pelo Python
        # channel.registerObject(  # Registra no comunicador "Channel" a nossa ponte
        #     "bridge",
        #     self.bridge,
        # )
        # self.browser.page().setWebChannel(channel)  # Define nosso channel

        self.browser.setUrl(
            QUrl.fromLocalFile(  # Isso aqui é o router, define as URL para que o usuário acesse isto
                str(HTML_DIR / "index.html")  # Neste caso é: HTML_DIR/index.html
            )
        )


app = QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()
