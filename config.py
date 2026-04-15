import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent
VIDEOS_JSON_PATH = BASE_DIR / "videos.json"
VECTOR_CACHE_PATH = BASE_DIR / "embeddings" / "cache" / "vectors.json"

# Embedding model (BGE-M3 — strong Vietnamese support, 1024-dim)
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024

# Chunking
CHUNK_MAX_CHARS = 500
CHUNK_OVERLAP_CHARS = 50

# Retrieval
TOP_K = 7
MIN_SIMILARITY = 0.25

# LLM-based reranking (uses Claude Haiku)
ENABLE_RERANKING = True
RERANK_TOP_K = 5
# Skip rerank when retrieval is already confident (top score >= threshold).
RERANK_SKIP_THRESHOLD = 0.7

# Query rewrite / intent (Haiku)
ENABLE_QUERY_REWRITE = True

# Claude LLM
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"          # final answer generation
CLAUDE_HAIKU_MODEL = "claude-haiku-4-5-20251001"   # rerank / rewrite / vision
MAX_TOKENS = 1024

# Data directories (multi-source pipeline)
RAW_DIR = BASE_DIR / "data" / "raw"
RAW_DOCS_DIR = RAW_DIR / "docs"
RAW_EXCEL_DIR = RAW_DIR / "excel"
RAW_IMAGES_DIR = RAW_DIR / "images"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
CHUNKS_JSONL_PATH = PROCESSED_DIR / "chunks.jsonl"
IMAGE_DESCRIPTIONS_PATH = PROCESSED_DIR / "image_descriptions.json"
BUILD_MANIFEST_PATH = PROCESSED_DIR / "build_manifest.json"

# Vietnamese query normalization (rule-based, lowercase-keyed)
QUERY_NORMALIZER: dict[str, str] = {
    "od": "OneDrive",
    "onedrive": "OneDrive",
    "outlook": "Outlook",
    "team": "Teams",
    "teams": "Teams",
    "authen": "Authenticator",
    "authenticator": "Authenticator",
    "xac thuc": "xác thực đa lớp",
    "xác thực": "xác thực đa lớp",
    "2fa": "xác thực đa lớp",
    "mfa": "xác thực đa lớp",
    "share": "chia sẻ",
    "sync": "đồng bộ",
    "upload": "tải lên",
    "download": "tải xuống",
}

# API server
API_HOST = "0.0.0.0"
API_PORT = 8000
