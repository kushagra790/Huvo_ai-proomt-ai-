from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agent import NorthstarAgent
from app.prompt import SYSTEM_PROMPT
from app.schemas import ChatRequest, ChatResponse, EndRequest, PromptResponse


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Northstar Homes Bot")
agent = NorthstarAgent()

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/prompt", response_model=PromptResponse)
def get_prompt() -> PromptResponse:
    return PromptResponse(prompt=SYSTEM_PROMPT)


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    result = agent.chat(request.message, request.session_id)
    return ChatResponse(**result)


@app.post("/api/end", response_model=ChatResponse)
def end(request: EndRequest) -> ChatResponse:
    result = agent.end(request.session_id)
    return ChatResponse(**result)


@app.get("/api/analytics/{session_id}")
def analytics(session_id: str) -> dict:
    state = agent.get_state(session_id)
    return agent.analytics(state)

