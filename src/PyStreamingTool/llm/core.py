from collections.abc import Mapping
from typing import Any

from ollama import Client, Message

from PyStreamingTool.llm.config import SYSTEM_PROMPT

from .config import OLLAMA_MODEL

ollama_client: Client | None = None


def get_active_client() -> Client:
    """Definimos com isto um client para o Ollama que não é iniciado à cada request"""
    global ollama_client
    if ollama_client is None:
        ollama_client = Client()
    return ollama_client


def shutdown_active_client() -> None:
    """Vou adicionar um método explicito para o encerramento da LLM junto da interface"""
    global ollama_client
    if ollama_client is not None:
        try:
            ollama_client.close()  # type: ignore[no-untyped-call]
        finally:
            ollama_client = None


class LlamaChat:
    def __init__(self) -> None:
        self._model = OLLAMA_MODEL

        self._messages: list[dict[str, Any]] = []  # Histórico do chat
        if SYSTEM_PROMPT:
            """
            A primeira mensagem do histórico sempre
            vai ser o system prompt para evitar
            envia-lo em todos os requests para o Ollama
            """
            self._messages.append({"role": "system", "content": SYSTEM_PROMPT})

    def chat(self, message: Mapping[str, Any] | Message) -> str | None:
        user_msg: dict[str, Any] = (  # Ao menos message.content tem que existir
            {"role": "user", "content": message["content"]}
            if isinstance(message, Mapping)
            else {"role": message.role, "content": message.content}
        )

        self._messages.append(user_msg)  # Envia mensagem do usuário

        response = get_active_client().chat(model=self._model, messages=self._messages) # type: ignore
        return response.message.content
