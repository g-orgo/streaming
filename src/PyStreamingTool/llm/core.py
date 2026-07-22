from typing import Any, Sequence, Mapping
from ollama import chat, Message  # type: ignore[reportUnknownVariableType]
from .config import OLLAMA_MODEL


class LlamaChat:
    def get_response(self, messages: Sequence[Mapping[str, Any] | Message] | None) -> str | None:
        response = chat(
            model=OLLAMA_MODEL,
            messages=messages,
        )
        return response.message.content
