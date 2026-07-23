from typing import Any, Mapping
from ollama import chat, Message  # type: ignore[reportUnknownVariableType]
from .config import OLLAMA_MODEL


class LlamaChat:
    def get_response(self, message: Mapping[str, Any] | Message) -> str | None:
        response = chat(
            model=OLLAMA_MODEL,
            messages=[message],
        )
        return response.message.content
