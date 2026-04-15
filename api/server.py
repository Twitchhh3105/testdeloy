"""FastAPI server for the RAG chatbot.

Architecture note: This server exposes POST /chat for the chatbot.
For future Teams integration, add botbuilder-core and a single
POST /api/messages endpoint that delegates to RAGChain.query().
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional
from pathlib import Path

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import config
from rag import RAGChain
from .schemas import ChatRequest, ChatResponse

app = FastAPI(title="M365 Video Assistant", version="1.0.0")

# Serve web UI static files
WEB_DIR = Path(__file__).parent.parent / "web"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared RAG chain (loaded once at startup)
rag_chain: Optional[RAGChain] = None

# In-memory session history (replace with Redis for production)
sessions: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY_TURNS = 10


@app.on_event("startup")
def startup():
    global rag_chain
    rag_chain = RAGChain()


@app.get("/health")
def health():
    return {"status": "ok", "model": config.CLAUDE_MODEL}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    history = sessions[req.session_id]

    result = rag_chain.query(req.message, history=history)

    # Update history
    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": result["answer"]})

    # Trim history to avoid token overflow
    if len(history) > MAX_HISTORY_TURNS * 2:
        sessions[req.session_id] = history[-(MAX_HISTORY_TURNS * 2):]

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        session_id=req.session_id,
        confidence=result.get("confidence", "high"),
        rewritten_query=result.get("rewritten_query", ""),
    )


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    history = sessions[req.session_id]
    history_snapshot = list(history)

    def event_generator():
        answer_parts: list[str] = []
        for event in rag_chain.query_stream(req.message, history=history_snapshot):
            if event["type"] == "done":
                answer_parts.append(event["answer"])
            payload = {k: v for k, v in event.items()}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        # Persist history after stream completes.
        final_answer = "".join(answer_parts)
        history.append({"role": "user", "content": req.message})
        history.append({"role": "assistant", "content": final_answer})
        if len(history) > MAX_HISTORY_TURNS * 2:
            sessions[req.session_id] = history[-(MAX_HISTORY_TURNS * 2):]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


# Mount static files AFTER API routes so /chat etc. take priority
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def run():
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)


if __name__ == "__main__":
    run()
