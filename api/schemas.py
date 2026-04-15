from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class SourceInfo(BaseModel):
    video: str
    nhom: str = ""
    chu_de: str = ""
    time: str = ""
    score: float = 0.0
    link: str = ""
    source_type: str = "video"
    rerank_score: Optional[float] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceInfo]
    session_id: str
    confidence: str = "high"
    rewritten_query: str = ""
