from collections.abc import Mapping
from typing import Any

from ollama import Client, Message

from PyStreamingTool.llm.config import SYSTEM_PROMPT

from .config import OLLAMA_MODEL


class LlamaChat:
    def __init__(self, message: Mapping[str, Any] | Message):
        self._client = Client()
        self._model = OLLAMA_MODEL
        user_msg: dict[str, Any] = (  # Ao menos message.content tem que existir
            {"role": "user", "content": message["content"]}
            if isinstance(message, Mapping)
            else {"role": message.role, "content": message.content}
        )

        self._messages: list[dict[str, Any]] = []  # Histórico do chat
        if SYSTEM_PROMPT:
            """
            A primeira mensagem do histórico sempre
            vai ser o system prompt para evitar
            envia-lo em todos os requests para o Ollama
            """
            self._messages.append({"role": "system", "content": SYSTEM_PROMPT})

        self._messages.append(user_msg)  # Envia mensagem do usuário

    def chat(self) -> str | None:
        response = self._client.chat(model=self._model, messages=self._messages)  # type: ignore
        return response.message.content
