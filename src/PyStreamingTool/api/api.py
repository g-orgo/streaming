from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from PyStreamingTool.llm.core import LlamaChat

app = FastAPI()
prefix = "/api/v1"
# session_history: list[dict[str, Any]] = []


class ChatRequest(BaseModel):
    user_input: str


@app.post(f"{prefix}/chat")
def chat_with_LLM(body: ChatRequest) -> dict[str, Any]:
    LlamaClient = LlamaChat()
    payload = LlamaClient.chat({"role": "user", "content": body.user_input})
    # session_history.append({"user": body.user_input, "LLM": payload})
    return {"output": payload}
