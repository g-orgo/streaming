from typing import Any

from pytestqt.qtbot import QtBot

from PyStreamingTool.ui.ui import MainWindow


def test_ui_initialize(qtbot: QtBot) -> None:
    """
    Valida que a estrutura principal
    do PySide6 de nosso projeto abre.
    """

    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.show()

    assert main_window.isVisible()


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

    def _register_html_element(value: Any) -> None:
        html_elements.append(value)

    main_window.browser.page().runJavaScript(
        'document.querySelector("#app") ?? ""', _register_html_element
    )
