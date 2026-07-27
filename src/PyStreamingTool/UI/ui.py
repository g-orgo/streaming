import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

from PyStreamingTool.ui.local_server import WEB_SOCKET, httpd, port

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
    """
    Aplicativo windows onde o usuário irá definir
    configurações e consultar dados
    """

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
        print(f"Aberto em: http://127.0.0.1:{port}/core/index.html")


class Legendas(QWidget):
    """
    Barra inferior do windows que apresentará legendas
    """

    def __init__(self) -> None:
        self.setWindowFlags(  # Aqui definiremos algumas configurações para a janela que criaremos
            Qt.WindowFlags(  # type: ignore
                Qt.WindowType.FramelessWindowHint  # Remove os botões que ficam no topo das aplicações
                | Qt.WindowType.WindowStaysOnTopHint  # Isso é o equivalente em javascript ao z-index, faz com que sempre esteja acima de qualquer outra aplicação
                | Qt.WindowType.Tool
                # Troca o tipo da aplicação para "ferramenta" o que
                # define vários comportamentos e é diferente em cada
                # sistema operacional (um exemplo é que pode remove-lo
                # do ALT+TAB, remove-lo da barra de aplicativos abertos,
                # etc...)
            )
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground  # Deve ter fundo translúcido
        )

        self.setStyleSheet(  # Define estilização CSS caso queira mudar o fundo ou a cor do texto por exemplo
            """ 
            Legendas { background-color: rgba(0,0,0,160); border-radius: 8px;}
            QLabel { color: #f0c960, font-size: 32px; font-weight: bold; padding: 6px 16px}
            """
        )
        self._label = QLabel("Teste de legenda")
        self._label.setWordWrap(
            True  # Textos devem quebrar para novas linhas quando atingirem o máximo do container automaticamente
        )
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignCenter  # Conteúdo deve ser centralizados no meio
        )
        layout = QVBoxLayout(
            self  # Criação da caixa (ou "container", "wrapper") que abrigará o restante da estrutura
        )
        layout.setContentsMargins(10, 5, 10, 5)
        layout.addWidget(self._label)
        self.posicionamento()

    def posicionamento(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            width = int(
                geo.width() * 0.6  # Ou seja, tem 60% da tela principal do usuário
            )
            # Aqui usei // para a divisão porquê com apenas / poderia dar um número quebrado e quero que arredonde
            x = (
                (geo.width() - width) // 2
            )  # Ou seja, quero metade de quanto tiver de largura desconsiderando o tamanho do app
            y = (
                geo.height() - 80
            )  # Considerando que na renderização a orientação é cima para baixo, quero 80px de diferença do máximo de altura (que é a parte mais baixa)
            self.setGeometry(x, y, width, 60)

    def texto_atual(self) -> str:
        return self._label.text()

    def mostrar_legenda(self) -> None:
        """Aqui ainda tenho que fazer o VAT"""
        return


app = QApplication(sys.argv)


def CloseApp() -> None:
    httpd.shutdown()
    WEB_SOCKET.close()
    app.quit()


def RunApp() -> None:
    """
    Isso impede que ao ser importado rode o aplicativo
    sem congelar. Isso é util para testes por exemplo.
    """
    window = MainWindow()

    shutdown_shortcut = QShortcut(QKeySequence("Ctrl+Q"), window)
    shutdown_shortcut.activated.connect(CloseApp)

    window.show()
    sys.exit(app.exec())
