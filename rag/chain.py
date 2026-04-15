from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path

import config
from embeddings.encoder import EmbeddingEncoder
from llm.claude_client import ClaudeClient
from .retriever import Retriever
from .prompt_builder import SYSTEM_PROMPT, build_context_block, format_sources


REWRITE_SYSTEM = (
    "Bạn là bộ phân tích câu hỏi về Microsoft 365. "
    "Nhiệm vụ: viết lại câu hỏi thành truy vấn tìm kiếm tự giải thích được, "
    "tách tự khoá, và nhận diện sản phẩm M365 liên quan. "
    "CHỈ trả về JSON hợp lệ, không giải thích thêm."
)


def _normalize_query(text: str, normalizer: dict[str, str]) -> str:
    """Rule-based Vietnamese query normalization (no LLM)."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not normalizer:
        return text
    out = text
    for key, repl in normalizer.items():
        pattern = re.compile(rf"\b{re.escape(key)}\b", re.IGNORECASE)
        out = pattern.sub(repl, out)
    return out


def _extract_confidence(top_score: float) -> str:
    if top_score >= 0.7:
        return "high"
    if top_score >= 0.4:
        return "medium"
    return "low"


class RAGChain:
    """Main RAG orchestrator: query -> retrieve -> rerank -> generate."""

    def __init__(self, vector_cache_path: str | Path | None = None):
        cache_path = vector_cache_path or config.VECTOR_CACHE_PATH

        self.encoder = EmbeddingEncoder(config.EMBEDDING_MODEL)

        cache_data = EmbeddingEncoder.load_cache(cache_path)
        self.retriever = Retriever(cache_data, self.encoder)

        self.llm = ClaudeClient(
            api_key=config.ANTHROPIC_API_KEY,
            model=config.CLAUDE_MODEL,
            max_tokens=config.MAX_TOKENS,
        )

    # --------------------------------------------------------------
    # Query rewrite (Haiku) — returns rewritten_query + keywords + product
    # --------------------------------------------------------------

    def _rewrite_query(
        self, question: str, history: list[dict]
    ) -> dict:
        history_text = ""
        if history:
            recent = history[-4:]
            history_text = "\n".join(
                f"{m['role']}: {m['content']}" for m in recent
            )

        prompt = (
            "Nhiệm vụ: phân tích câu hỏi về Microsoft 365 và viết lại thành "
            "câu tìm kiếm tối ưu.\n\n"
            f"Lịch sử hội thoại:\n{history_text or '(không có)'}\n\n"
            f"Câu hỏi hiện tại: {question}\n\n"
            "Trả về JSON đúng định dạng:\n"
            '{"rewritten_query": "...", "keywords": ["..."], '
            '"product": "Teams|Outlook|OneDrive|Authenticator|SharePoint|Other"}'
        )
        try:
            raw = self.llm.quick_text(
                model=config.CLAUDE_HAIKU_MODEL,
                system_prompt=REWRITE_SYSTEM,
                user_content=prompt,
                max_tokens=400,
            )
            data = _parse_json(raw)
            if not isinstance(data, dict):
                raise ValueError("not a dict")
            data.setdefault("rewritten_query", question)
            data.setdefault("keywords", [])
            data.setdefault("product", "Other")
            return data
        except Exception:
            return {"rewritten_query": question, "keywords": [], "product": "Other"}

    # --------------------------------------------------------------
    # Main entry point
    # --------------------------------------------------------------

    def _prepare(
        self,
        user_question: str,
        history: list[dict] | None,
        top_k: int | None,
    ) -> tuple[str, str, list[dict], str, list[dict], float]:
        """Shared prep for query/query_stream.

        Returns (system_prompt, context_block, messages, search_query, chunks, top_score).
        """
        k = top_k or config.TOP_K
        t_total = time.perf_counter()

        # 1. Rule-based normalization (always on)
        t0 = time.perf_counter()
        normalized = _normalize_query(user_question, config.QUERY_NORMALIZER)
        print(f"[TIMING] normalize: {time.perf_counter() - t0:.3f}s")

        # 2. Haiku rewrite — only when needed:
        #    - history present (coreference resolution)
        #    - query is very short/ambiguous (< 4 words)
        t0 = time.perf_counter()
        rewrite = {"rewritten_query": normalized, "keywords": [], "product": "Other"}
        rewrite_ran = False
        needs_rewrite = bool(history) or len(normalized.split()) < 4
        if config.ENABLE_QUERY_REWRITE and needs_rewrite:
            rewrite = self._rewrite_query(normalized, history or [])
            rewrite_ran = True
        print(f"[TIMING] rewrite_query: {time.perf_counter() - t0:.3f}s (ran={rewrite_ran})")

        search_query = rewrite.get("rewritten_query") or normalized
        extra_keywords = rewrite.get("keywords") or []
        product_filter = rewrite.get("product") or "Other"

        # 3. Retrieve
        t0 = time.perf_counter()
        chunks = self.retriever.search(
            search_query,
            top_k=k,
            min_similarity=config.MIN_SIMILARITY,
            extra_keywords=extra_keywords,
            product_hint=product_filter,
        )
        print(f"[TIMING] retrieval_total: {time.perf_counter() - t0:.3f}s")

        # 4. Optional rerank with Haiku — skip when top score already "high"
        #    or too few chunks to benefit.
        t0 = time.perf_counter()
        rerank_ran = False
        if config.ENABLE_RERANKING and len(chunks) >= 3:
            pre_top = max((c.get("score", 0.0) for c in chunks), default=0.0)
            if pre_top < config.RERANK_SKIP_THRESHOLD:
                chunks = self._rerank_with_haiku(search_query, chunks)
                rerank_ran = True
        print(f"[TIMING] rerank: {time.perf_counter() - t0:.3f}s (ran={rerank_ran})")

        # 5. Confidence indicator
        top_score = max(
            (c.get("rerank_score") or c.get("score", 0.0) for c in chunks),
            default=0.0,
        )
        confidence = _extract_confidence(top_score)

        # 6. Build prompt & generate
        context_block = build_context_block(chunks)
        messages = list(history or [])
        messages.append({"role": "user", "content": user_question})

        system_with_confidence = SYSTEM_PROMPT
        if confidence == "medium":
            system_with_confidence += (
                "\n\nLƯU Ý: độ tin cậy trung bình. Bắt đầu câu trả lời bằng cụm "
                '"Dựa trên thông tin hiện có,".'
            )
        elif confidence == "low":
            system_with_confidence += (
                "\n\nLƯU Ý: độ tin cậy thấp. Nói rõ rằng bạn không chắc chắn và "
                "đề nghị người dùng cung cấp thêm thông tin hoặc kiểm tra trực tiếp."
            )

        print(f"[TIMING] prep_total: {time.perf_counter() - t_total:.3f}s")
        return (
            system_with_confidence,
            context_block,
            messages,
            search_query,
            chunks,
            top_score,
        )

    def query(
        self,
        user_question: str,
        history: list[dict] | None = None,
        top_k: int | None = None,
    ) -> dict:
        t_total = time.perf_counter()
        system_prompt, context_block, messages, search_query, chunks, top_score = (
            self._prepare(user_question, history, top_k)
        )
        confidence = _extract_confidence(top_score)

        t0 = time.perf_counter()
        answer = self.llm.generate(system_prompt, context_block, messages)
        print(f"[TIMING] claude_generate: {time.perf_counter() - t0:.3f}s")
        print(f"[TIMING] total: {time.perf_counter() - t_total:.3f}s")

        return {
            "answer": answer,
            "sources": format_sources(chunks),
            "confidence": confidence,
            "rewritten_query": search_query,
            "product": "",
        }

    def query_stream(
        self,
        user_question: str,
        history: list[dict] | None = None,
        top_k: int | None = None,
    ):
        """Yields dict events: {'type': 'meta'|'delta'|'done', ...}.

        meta fires once before generation starts (so client can render sources
        immediately); delta fires per text chunk; done fires at the end with the
        full answer for history persistence.
        """
        t_total = time.perf_counter()
        system_prompt, context_block, messages, search_query, chunks, top_score = (
            self._prepare(user_question, history, top_k)
        )
        confidence = _extract_confidence(top_score)

        yield {
            "type": "meta",
            "sources": format_sources(chunks),
            "confidence": confidence,
            "rewritten_query": search_query,
        }

        t0 = time.perf_counter()
        parts: list[str] = []
        first_token_logged = False
        for delta in self.llm.generate_stream(system_prompt, context_block, messages):
            if not first_token_logged:
                print(f"[TIMING] first_token: {time.perf_counter() - t0:.3f}s")
                first_token_logged = True
            parts.append(delta)
            yield {"type": "delta", "text": delta}
        print(f"[TIMING] claude_stream_total: {time.perf_counter() - t0:.3f}s")
        print(f"[TIMING] total: {time.perf_counter() - t_total:.3f}s")

        yield {"type": "done", "answer": "".join(parts)}

    # --------------------------------------------------------------
    # Reranking via Haiku (silent fallback on failure)
    # --------------------------------------------------------------

    def _rerank_with_haiku(
        self, query: str, chunks: list[dict]
    ) -> list[dict]:
        numbered = "\n\n".join(
            f"[{i + 1}] {c.get('text_raw') or c.get('text', '')[:500]}"
            for i, c in enumerate(chunks)
        )
        user_prompt = (
            "Bạn là hệ thống đánh giá độ liên quan. Cho câu hỏi và các đoạn văn bản, "
            "hãy chấm điểm mức độ liên quan từ 0.0 đến 1.0. Trả về ONLY một JSON "
            "array điểm số theo đúng thứ tự, không giải thích.\n\n"
            f"Câu hỏi: {query}\n\nCác đoạn văn:\n{numbered}\n\n"
            "Trả về: [0.85, 0.3, ...]"
        )
        try:
            raw = self.llm.quick_text(
                model=config.CLAUDE_HAIKU_MODEL,
                system_prompt="Bạn là hệ thống chấm điểm relevance.",
                user_content=user_prompt,
                max_tokens=200,
            )
            scores = _parse_json(raw)
            if not isinstance(scores, list) or len(scores) != len(chunks):
                return chunks
            for c, s in zip(chunks, scores):
                try:
                    c["rerank_score"] = float(s)
                except (TypeError, ValueError):
                    c["rerank_score"] = c.get("score", 0.0)
            chunks.sort(key=lambda c: c.get("rerank_score", 0), reverse=True)
            return chunks[: config.RERANK_TOP_K]
        except Exception:
            return chunks


def _parse_json(text: str):
    text = text.strip()
    # Strip ```json fences if present
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    # Fallback: find first JSON-looking substring
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise
