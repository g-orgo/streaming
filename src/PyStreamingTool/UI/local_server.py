import http.server
import socket
import threading
from pathlib import Path
from typing import Any

UI_DIR = Path(__file__).parent
WEB_SOCKET = socket.socket()


def _find_free_port() -> int:
    WEB_SOCKET.bind(("", 0))
    return WEB_SOCKET.getsockname()[1]


class _HttpHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        # print(self, format, *args) # Aqui só seria necessário se eu quisesse alterar as mensagens padrões do sistema.
        pass


port = _find_free_port()
httpd = http.server.HTTPServer(("127.0.0.1", port), _HttpHandler)

threading.Thread(target=httpd.serve_forever, daemon=True).start()
