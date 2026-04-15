from __future__ import annotations

import re
import time
from collections import Counter

import numpy as np

from embeddings.encoder import EmbeddingEncoder

SAME_VIDEO_BOOST = 0.06
KEYWORD_BOOST = 0.05
PRODUCT_BOOST = 0.04
MAX_CHUNKS_PER_VIDEO = 3

PRODUCT_NHOM_HINTS: dict[str, list[str]] = {
    "Teams": ["teams"],
    "Outlook": ["outlook", "email", "thư", "chữ ký"],
    "OneDrive": ["onedrive", "đồng bộ", "tài liệu cá nhân"],
    "Authenticator": ["authenticator", "xác thực", "đăng nhập"],
    "SharePoint": ["sharepoint", "chia sẻ"],
}


def _extract_keywords(text: str) -> set[str]:
    words = re.findall(r"[\w]+", text.lower())
    stopwords = {
        "làm", "sao", "cách", "như", "thế", "nào", "gì", "được", "trong",
        "của", "và", "cho", "các", "một", "khi", "với", "theo", "bạn",
        "đã", "có", "không", "này", "đó", "là", "để", "từ", "trên",
        "về", "hay", "hoặc", "nhưng", "nếu", "thì", "mà", "còn",
        "rồi", "nữa", "hãy", "cần", "phải", "xong", "tôi", "mình",
    }
    return {w for w in words if len(w) >= 2 and w not in stopwords}


class Retriever:
    def __init__(self, cache_data: dict, encoder: EmbeddingEncoder):
        self.encoder = encoder
        cache_model = cache_data.get("model_name") or cache_data.get("model")
        if cache_model and cache_model != encoder.model_name:
            raise RuntimeError(
                f"Vector cache was built with model '{cache_model}' but the "
                f"encoder is using '{encoder.model_name}'. "
                f"Run: python scripts/build_vectors.py"
            )
        self.chunks = cache_data["chunks"]
        self.embeddings = np.array(
            [c["embedding"] for c in self.chunks], dtype=np.float32
        )
        self._video_indices: dict[str, list[int]] = {}
        for i, c in enumerate(self.chunks):
            key = c.get("video_name") or c.get("file_name") or ""
            self._video_indices.setdefault(key, []).append(i)

        # Pre-compute keyword sets + product haystacks once at startup so the
        # hot path in search() does no per-chunk tokenization.
        self._chunk_keywords: list[set[str]] = []
        self._chunk_product_haystack: list[str] = []
        for c in self.chunks:
            text = (
                (c.get("text_embed") or c.get("text", ""))
                + " "
                + str(c.get("chu_de", ""))
                + " "
                + str(c.get("video_name", ""))
                + " "
                + str(c.get("section", ""))
                + " "
                + str(c.get("topic", ""))
            ).lower()
            self._chunk_keywords.append(_extract_keywords(text))
            self._chunk_product_haystack.append(
                (
                    str(c.get("nhom", ""))
                    + " "
                    + str(c.get("product", ""))
                    + " "
                    + str(c.get("chu_de", ""))
                    + " "
                    + str(c.get("video_name", ""))
                ).lower()
            )

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.25,
        extra_keywords: list[str] | None = None,
        product_hint: str | None = None,
        filters: dict | None = None,
    ) -> list[dict]:
        """Hybrid retrieval with optional keyword / product / source-type filters."""
        t0 = time.perf_counter()
        query_emb = self.encoder.encode_query(query)
        print(f"[TIMING]   encode_query: {time.perf_counter() - t0:.3f}s")

        t0 = time.perf_counter()
        scores = self.embeddings @ query_emb.astype(np.float32)
        print(f"[TIMING]   cosine_matmul: {time.perf_counter() - t0:.3f}s")
        t_boost = time.perf_counter()

        # Source-type filter (multi-source support)
        allow = np.ones(len(self.chunks), dtype=bool)
        if filters:
            for field, expected in filters.items():
                for i, c in enumerate(self.chunks):
                    if c.get(field) != expected:
                        allow[i] = False

        # Keyword boost (uses pre-computed chunk keyword sets)
        query_kw = _extract_keywords(query)
        if extra_keywords:
            for kw in extra_keywords:
                query_kw |= _extract_keywords(kw)
        if query_kw:
            for i, chunk_kw in enumerate(self._chunk_keywords):
                overlap = len(query_kw & chunk_kw)
                if overlap:
                    scores[i] += KEYWORD_BOOST * min(overlap, 3)

        # Product hint boost (soft filter on nhom / product fields)
        if product_hint and product_hint != "Other":
            hints = PRODUCT_NHOM_HINTS.get(product_hint, [product_hint.lower()])
            for i, haystack in enumerate(self._chunk_product_haystack):
                if any(h in haystack for h in hints):
                    scores[i] += PRODUCT_BOOST

        # Sibling video boost
        visible = scores.copy()
        visible[~allow] = -1e9
        preliminary = np.argsort(visible)[::-1][: top_k * 2]
        video_counts = Counter(
            self.chunks[int(idx)].get("video_name", "") for idx in preliminary
        )
        boosted = scores.copy()
        for video_name, count in video_counts.items():
            if not video_name or video_name not in self._video_indices:
                continue
            boost = SAME_VIDEO_BOOST if count >= 2 else SAME_VIDEO_BOOST * 0.5
            for idx in self._video_indices[video_name]:
                boosted[idx] += boost

        boosted[~allow] = -1e9

        # Rank with diversity cap
        ranked_indices = np.argsort(boosted)[::-1]
        results: list[dict] = []
        video_hit_count: Counter = Counter()
        for idx in ranked_indices:
            if len(results) >= top_k:
                break
            score = float(boosted[idx])
            if score < min_similarity:
                break
            video = self.chunks[idx].get("video_name") or self.chunks[idx].get(
                "file_name", ""
            )
            if video and video_hit_count[video] >= MAX_CHUNKS_PER_VIDEO:
                continue
            video_hit_count[video] += 1
            chunk = {k: v for k, v in self.chunks[idx].items() if k != "embedding"}
            chunk["score"] = round(score, 4)
            results.append(chunk)

        print(f"[TIMING]   boost_rank: {time.perf_counter() - t_boost:.3f}s")
        return results
