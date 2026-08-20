from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    ended: bool
    memory: dict[str, Any]
    analytics: dict[str, Any]


class EndRequest(BaseModel):
    session_id: str


class PromptResponse(BaseModel):
    prompt: str

