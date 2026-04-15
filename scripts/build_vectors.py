"""Build unified vector cache from videos + documents + excel + images.

Usage:
    python scripts/build_vectors.py              # incremental (videos only today)
    python scripts/build_vectors.py --full       # full multi-source rebuild
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from data import load_videos, chunk_videos
from embeddings import EmbeddingEncoder


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()


def _load_existing_cache_model() -> str | None:
    try:
        data = EmbeddingEncoder.load_cache(config.VECTOR_CACHE_PATH)
        return data.get("model_name") or data.get("model")
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _chunks_from_videos() -> list[dict]:
    videos = load_videos(config.VIDEOS_JSON_PATH)
    print(f"Loaded {len(videos)} videos with transcripts")
    chunks = chunk_videos(
        videos,
        max_chars=config.CHUNK_MAX_CHARS,
        overlap_chars=config.CHUNK_OVERLAP_CHARS,
    )
    print(
        f"Created {len(chunks)} video chunks "
        f"({sum(1 for c in chunks if c.chunk_type == 'summary')} summary + "
        f"{sum(1 for c in chunks if c.chunk_type == 'transcript')} transcript)"
    )
    return [c.to_dict() for c in chunks]


def _chunks_from_docs() -> list[dict]:
    try:
        from data.loaders.doc_loader import load_documents
        from data.cleaners.doc_cleaner import clean_document
        from data.chunkers.doc_chunker import chunk_document
    except Exception as exc:
        print(f"[docs] skipped ({exc})")
        return []
    out: list[dict] = []
    if not config.RAW_DOCS_DIR.exists():
        return out
    for doc in load_documents(config.RAW_DOCS_DIR):
        cleaned = clean_document(doc)
        out.extend(chunk_document(cleaned))
    print(f"Created {len(out)} document chunks")
    return out


def _chunks_from_excel() -> list[dict]:
    try:
        from data.loaders.excel_loader import load_excel_files
        from data.cleaners.excel_cleaner import clean_sheet
        from data.chunkers.excel_chunker import chunk_sheet
    except Exception as exc:
        print(f"[excel] skipped ({exc})")
        return []
    out: list[dict] = []
    if not config.RAW_EXCEL_DIR.exists():
        return out
    for sheet in load_excel_files(config.RAW_EXCEL_DIR):
        cleaned = clean_sheet(sheet)
        out.extend(chunk_sheet(cleaned))
    print(f"Created {len(out)} excel chunks")
    return out


def _chunks_from_images() -> list[dict]:
    try:
        from data.loaders.image_loader import load_images
        from data.cleaners.image_cleaner import describe_images
        from data.chunkers.image_chunker import chunk_image
    except Exception as exc:
        print(f"[images] skipped ({exc})")
        return []
    out: list[dict] = []
    if not config.RAW_IMAGES_DIR.exists():
        return out
    images = list(load_images(config.RAW_IMAGES_DIR))
    if not images:
        return out
    descriptions = describe_images(images, cache_path=config.IMAGE_DESCRIPTIONS_PATH)
    for img in images:
        desc = descriptions.get(img["file_name"])
        if not desc:
            continue
        out.append(chunk_image(img, desc))
    print(f"Created {len(out)} image chunks")
    return out


def _write_manifest(all_chunks: list[dict], sources: dict[str, str]) -> None:
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "model_name": config.EMBEDDING_MODEL,
        "last_build": datetime.now(timezone.utc).isoformat(),
        "total_chunks": len(all_chunks),
        "processed_files": sources,
    }
    with open(config.BUILD_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    # Dump chunks.jsonl for inspection
    with open(config.CHUNKS_JSONL_PATH, "w", encoding="utf-8") as f:
        for c in all_chunks:
            out = {k: v for k, v in c.items() if k != "embedding"}
            f.write(json.dumps(out, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full rebuild across all sources (videos + docs + excel + images).",
    )
    args = parser.parse_args()

    print("=== Building Vector Cache ===\n")

    existing_model = _load_existing_cache_model()
    if existing_model and existing_model != config.EMBEDDING_MODEL:
        print(
            f"⚠️  Cache was built with '{existing_model}', "
            f"config says '{config.EMBEDDING_MODEL}'. Rebuilding.\n"
        )

    all_chunks: list[dict] = []
    sources: dict[str, str] = {}

    all_chunks.extend(_chunks_from_videos())
    if config.VIDEOS_JSON_PATH.exists():
        sources["videos.json"] = _sha256(config.VIDEOS_JSON_PATH)

    if args.full:
        all_chunks.extend(_chunks_from_docs())
        all_chunks.extend(_chunks_from_excel())
        all_chunks.extend(_chunks_from_images())

    print(f"\nTotal chunks: {len(all_chunks)}")

    encoder = EmbeddingEncoder(config.EMBEDDING_MODEL)
    encoder.build_cache_from_dicts(all_chunks, config.VECTOR_CACHE_PATH)

    _write_manifest(all_chunks, sources)
    print("\nDone!")


if __name__ == "__main__":
    main()
