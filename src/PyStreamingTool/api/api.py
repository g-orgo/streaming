from pydantic import BaseModel
from typing import Any
from fastapi import FastAPI
from PyStreamingTool.llm.core import LlamaChat

app = FastAPI()
prefix = "/api/v1"
session_history: list[dict[str, Any]] = []

class ChatRequest(BaseModel):
    user_input: str


@app.post(f"{prefix}/chat")
def chat_with_LLM(body: ChatRequest) -> dict[str, Any]:
    chat = LlamaChat()
    payload = chat.get_response({"role": "user", "content": body.user_input})
    session_history.append({"user": body.user_input, "LLM": payload})
    return {"output": payload}
