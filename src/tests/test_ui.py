# noqa: N999

from typing import Any

from PySide6.QtCore import QEventLoop, QTimer
from pytestqt.qtbot import QtBot

from PyStreamingTool.ui.ui import MainWindow


def test_ui_initialize(qtbot: QtBot) -> None:
    """
    Valida que a estrutura principal do
    nosso projeto abre
    """

    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.show()

    assert main_window.isVisible()
    return print("test_ui_initialize")


def test_if_it_has_app_div(qtbot: QtBot) -> None:
    """
    Valida que dentro da estrutura gerada
    temos o elemento onde roda os .jsx
    """

    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.show()

    with qtbot.waitSignal(main_window.browser.loadFinished, timeout=10000) as result:
        pass  # Aguarda a página carregar

    assert result.args[0] is True  # type:ignore
    """ Ou seja, carregou. """

    html_elements: list[Any] = []
    loop = QEventLoop()

    main_window.browser.page().runJavaScript(
        'document.querySelector("#app") ?? ""',
        lambda value: (html_elements.append(value), loop.quit()),  # type: ignore
    )

    QTimer.singleShot(5000, loop.quit)
    loop.exec()

    """
    O que acabamos de fazer aqui com loop e loop.exec() é 
    definirmos um anel de tempo e dizer quando ele deve rodar.
    Quando loop.exec() é iniciado ele congela a execução dos
    arquivo enquanto o nosso runJavaScript (ou qualquer evento Qt)
    segue em segundo plano; e ao final do método ocorre
    loop.quit() causando o fim do anel. Por isso usamos o
    QTimer.singleShot, é um método "anticongelamento"
    que encerre o loop após um X período sendo ele bem
    sucedido ou não
    """

    assert len(html_elements) > 0
    print(test_if_it_has_app_div)
