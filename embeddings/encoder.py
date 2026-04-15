from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from data.chunker import Chunk


def _pick_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


class EmbeddingEncoder:
    def __init__(self, model_name: str, device: str | None = None):
        self.model_name = model_name
        self.device = device or _pick_device()
        self.model = SentenceTransformer(model_name, device=self.device)

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(
            texts,
            show_progress_bar=True,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

    def encode_query(self, query: str) -> np.ndarray:
        return self.model.encode(
            [query], normalize_embeddings=True, convert_to_numpy=True
        )[0]

    def build_cache(self, chunks: list[Chunk], cache_path: str | Path) -> None:
        texts = [c.text_embed for c in chunks]
        embeddings = self.encode_texts(texts)

        cache_data = {
            "model_name": self.model_name,
            "model": self.model_name,  # legacy key
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_chunks": len(chunks),
            "chunks": [],
        }

        for chunk, emb in zip(chunks, embeddings):
            entry = chunk.to_dict()
            entry["embedding"] = emb.tolist()
            cache_data["chunks"].append(entry)

        cache_path = Path(cache_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

        print(
            f"Cached {len(chunks)} chunk embeddings "
            f"(model={self.model_name}, device={self.device}) -> {cache_path}"
        )

    def build_cache_from_dicts(
        self, chunk_dicts: list[dict], cache_path: str | Path
    ) -> None:
        """Embed pre-built chunk dicts (multi-source pipeline)."""
        texts = [c.get("text_embed") or c.get("text_raw", "") for c in chunk_dicts]
        embeddings = self.encode_texts(texts)

        cache_data = {
            "model_name": self.model_name,
            "model": self.model_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_chunks": len(chunk_dicts),
            "chunks": [],
        }
        for chunk, emb in zip(chunk_dicts, embeddings):
            entry = dict(chunk)
            entry["embedding"] = emb.tolist()
            cache_data["chunks"].append(entry)

        cache_path = Path(cache_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

        print(
            f"Cached {len(chunk_dicts)} chunks "
            f"(model={self.model_name}, device={self.device}) -> {cache_path}"
        )

    @staticmethod
    def load_cache(cache_path: str | Path) -> dict:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
