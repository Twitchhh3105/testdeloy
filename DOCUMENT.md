# M365 Video QA Assistant - Project Documentation

## Tổng quan

Hệ thống chatbot hỏi đáp (Q&A) đa nguồn dựa trên nội dung **video hướng dẫn, tài liệu văn bản (DOCX/PDF/TXT), bảng tính Excel/CSV và ảnh chụp màn hình** về Microsoft 365 (Teams, Outlook, OneDrive, Authenticator, SharePoint…). Sử dụng kiến trúc **RAG (Retrieval-Augmented Generation)** với reranking và query rewrite để trả lời câu hỏi bằng tiếng Việt, có trích dẫn nguồn kèm mốc thời gian.

---

## Cấu trúc thư mục

```
Claude_QA_Video/
├── config.py                  # Cấu hình chung (model, tham số, QUERY_NORMALIZER)
├── videos.json                # Dữ liệu video gốc (input chính)
├── requirements.txt           # Thư viện Python
├── .env                       # ANTHROPIC_API_KEY
│
├── data/
│   ├── loader.py              # Đọc videos.json
│   ├── cleaner.py             # Làm sạch transcript (STT fix, normalize)
│   ├── chunker.py             # Chunk video với text_raw / text_embed
│   │
│   ├── loaders/               # [MỚI] Loaders đa nguồn
│   │   ├── doc_loader.py      # .docx (python-docx) / .pdf (pdfplumber) / .txt
│   │   ├── excel_loader.py    # .xlsx/.xls (openpyxl) / .csv (pandas)
│   │   └── image_loader.py    # .png/.jpg/.jpeg/.webp (Pillow)
│   │
│   ├── cleaners/              # [MỚI] Cleaners đa nguồn
│   │   ├── doc_cleaner.py     # Boilerplate, bullets, hyphenation, NFC
│   │   ├── excel_cleaner.py   # NFC cell, date DD/MM/YYYY, merged rows
│   │   └── image_cleaner.py   # Gọi Claude Haiku vision + cache JSON
│   │
│   ├── chunkers/              # [MỚI] Chunkers đa nguồn
│   │   ├── doc_chunker.py     # H2-section chunks + table-as-chunk
│   │   ├── excel_chunker.py   # Strategy A (>20 rows) / Strategy B
│   │   └── image_chunker.py   # Vision JSON → text_raw / text_embed
│   │
│   ├── raw/                   # [MỚI] Nguyên liệu đa nguồn
│   │   ├── docs/              # Thả .docx / .pdf / .txt vào đây
│   │   ├── excel/             # Thả .xlsx / .xls / .csv vào đây
│   │   └── images/            # Thả .png / .jpg / .webp vào đây
│   │
│   └── processed/             # [MỚI] Artifacts của pipeline build
│       ├── chunks.jsonl              # Toàn bộ chunk (debug / audit)
│       ├── image_descriptions.json   # Cache kết quả Claude vision
│       └── build_manifest.json       # Model, timestamp, sha256 nguồn
│
├── embeddings/
│   ├── encoder.py             # BGE-M3 encoder (GPU/MPS/CPU fallback)
│   └── cache/vectors.json     # Vector cache thống nhất cho mọi nguồn
│
├── rag/
│   ├── chain.py               # Orchestrator: normalize → rewrite → retrieve → rerank → generate
│   ├── retriever.py           # Hybrid + keyword/product boost + source-type filter
│   └── prompt_builder.py      # System prompt + context block + format_sources
│
├── llm/
│   └── claude_client.py       # Sonnet (answer) + quick_text (Haiku rerank/rewrite/vision)
│
├── api/
│   ├── server.py              # FastAPI; trả về confidence + rewritten_query
│   └── schemas.py             # SourceInfo giờ có source_type + rerank_score
│
├── web/
│   ├── index.html             # 6 suggestion chips mới
│   ├── style.css              # source-card, confidence badge, copy button
│   └── app.js                 # Source cards [VIDEO]/[DOC]/[EXCEL]/[IMAGE], copy, typing
│
├── scripts/
│   ├── build_vectors.py       # [REWRITE] Pipeline đa nguồn + --full + manifest
│   ├── eval_retrieval.py      # [MỚI] Hit@1 / Hit@3 / MRR
│   └── chat_cli.py
│
├── bot/                       # (Dự phòng) Tích hợp Teams bot
└── video/                     # File video gốc
```

---

## Input

### 1. `videos.json` — Video gốc

Không đổi so với schema cũ (`name`, `nhom`, `chu_de`, `noi_dung`, `transcript`, `links`).

### 2. `data/raw/` — [MỚI] Nguồn bổ sung

| Thư mục    | Định dạng hỗ trợ           | Ghi chú                                              |
| ---------- | -------------------------- | ----------------------------------------------------- |
| `docs/`    | `.docx`, `.pdf`, `.txt`    | PDF chỉ hỗ trợ text-based (không OCR)                |
| `excel/`   | `.xlsx`, `.xls`, `.csv`    | Multi-sheet; tự chọn Strategy A/B theo số dòng       |
| `images/`  | `.png`, `.jpg`, `.webp`    | Skip ảnh <100×100px; mô tả bằng Claude Haiku vision |

### 3. `.env`

```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### 4. User Input

Hai endpoint song song:

- **`POST /chat`** — non-stream, trả JSON một lần (giữ tương thích cũ).
- **`POST /chat/stream`** — Server-Sent Events, stream sources + tokens từng phần (giảm perceived latency xuống ~1s).

```json
{ "message": "Làm sao để đồng bộ OneDrive?", "session_id": "user-123" }
```

---

## Output

### API Response (`POST /chat`)

```json
{
  "answer": "Để đồng bộ OneDrive với máy tính, bạn thực hiện các bước sau...",
  "sources": [
    {
      "video": "Đồng bộ dữ liệu từ cloud về máy tính cá nhân.mp4",
      "nhom": "Hướng dẫn sử dụng OneDrive",
      "chu_de": "Đồng bộ dữ liệu từ cloud về máy tính cá nhân",
      "time": "00:00",
      "score": 0.782,
      "rerank_score": 0.91,
      "source_type": "video",
      "link": "https://youtube.com/..."
    }
  ],
  "session_id": "user-123",
  "confidence": "high",
  "rewritten_query": "hướng dẫn đồng bộ OneDrive về máy tính"
}
```

Trường mới so với phiên bản trước:

| Trường            | Mô tả                                                                 |
| ----------------- | ---------------------------------------------------------------------- |
| `source_type`     | `video` / `document` / `excel` / `image` — hiển thị làm label trên UI |
| `rerank_score`    | Điểm LLM rerank (nếu `ENABLE_RERANKING = True`)                       |
| `confidence`      | `high` (top ≥ 0.7) / `medium` (0.4–0.7) / `low` (<0.4)                |
| `rewritten_query` | Câu truy vấn đã được Haiku viết lại (debug / hiển thị)                |

### Streaming Response (`POST /chat/stream`)

Content-type `text/event-stream`. Mỗi frame là một dòng `data: {json}\n\n` với 3 loại event:

```
data: {"type":"meta","sources":[...],"confidence":"high","rewritten_query":"..."}

data: {"type":"delta","text":"Để đồng "}
data: {"type":"delta","text":"bộ OneDrive..."}
...
data: {"type":"done","answer":"<full text>"}
```

- `meta` phát ngay khi retrieval + rerank xong (~0.2s sau request) để UI render sources trước.
- `delta` phát từng đoạn text do Claude stream về (first token ~1s).
- `done` phát cuối với `answer` đầy đủ để client persist history.

---

## Pipeline

### Phase 1 — Offline: Build Vector Cache

**Lệnh:** `python scripts/build_vectors.py` (chỉ videos) hoặc `python scripts/build_vectors.py --full` (đa nguồn).

```
videos.json ───┐
               │
data/raw/docs/ ─┼──► Load → Clean → Chunk ─┐
data/raw/excel/┤                           │
data/raw/images/ (Claude Haiku vision,     │
                  cache image_descriptions.json)
               │                           │
               ▼                           ▼
         Merged chunk list (source_type = video|document|excel|image)
                           │
                           ▼
              BGE-M3 (BAAI/bge-m3, 1024-dim, GPU/MPS/CPU)
                           │
                           ▼
           embeddings/cache/vectors.json (model_name được nhúng)
                           │
                           ▼
          data/processed/build_manifest.json (+ chunks.jsonl)
```

**Chi tiết chunk schema mới:**

```json
{
  "text_raw":    "...",        // Hiển thị cho người dùng & làm context LLM
  "text_embed":  "[Video: ... | Nhóm: ... | Chủ đề: ... | Thời gian: 00:45]\n...",
  "source_type": "video",      // video | document | excel | image
  "chunk_index": 2,
  "total_chunks": 8,
  "chunk_type":  "transcript"  // transcript | summary | doc_section | doc_table
                               //   | excel_rows | excel_summary | image_description
}
```

### Phase 2 — Online: Trả lời câu hỏi

```
User question + history
        │
        ▼
 Step 0a: Rule-based normalize       rag/chain.py::_normalize_query
          NFC + QUERY_NORMALIZER     (KHÔNG gọi API)
        │
        ▼
 Step 0b: Haiku query rewrite         rag/chain.py::_rewrite_query
          → { rewritten_query,        (claude-haiku-4-5-20251001)
              keywords[],             [GATE] chỉ chạy khi có history
              product }                      hoặc query < 4 từ
        │
        ▼
 Step 1:  Hybrid Retrieval            rag/retriever.py
          cosine + keyword_boost
          + product_boost (nhom/product/chu_de)
          + sibling-video boost
          + max 3 chunks / nguồn
          + tùy chọn filters={source_type: ...}
        │
        ▼
 Step 2:  LLM Reranking (optional)    rag/chain.py::_rerank_with_haiku
          Claude Haiku chấm 0..1      (silent fallback khi lỗi)
          → giữ top RERANK_TOP_K = 5  [GATE] skip khi top_score >= 0.7
                                              hoặc len(chunks) < 3
        │
        ▼
 Step 3:  Confidence tier
          top ≥ 0.7 → high
          0.4–0.7   → medium  (prepend "Dựa trên thông tin hiện có,")
          < 0.4     → low     (gợi ý user clarify)
        │
        ▼
 Step 4:  Build context + Generate    llm/claude_client.py
          Sonnet 4, max_tokens=1024    .generate()         → non-stream (/chat)
          Prompt caching (ephemeral)   .generate_stream()  → SSE       (/chat/stream)
        │
        ▼
   { answer, sources, confidence, rewritten_query }   (non-stream)
   meta → delta* → done                               (stream)
```

Mọi bước đều có timing log `[TIMING] <step>: X.XXXs` in ra stdout để debug/profile.

---

## Thay đổi so với bản cũ (Changelog)

### 1. Embedding model
- **Cũ:** `paraphrase-multilingual-MiniLM-L12-v2` (384-dim).
- **Mới:** `BAAI/bge-m3` (1024-dim, hỗ trợ tiếng Việt tốt hơn).
- Encoder tự chọn `cuda` / `mps` / `cpu`.
- `Retriever` raise lỗi rõ ràng khi cache không khớp model → yêu cầu rebuild.

### 2. Contextual chunk enrichment
- Mỗi chunk có **`text_raw`** (hiển thị) và **`text_embed`** (thêm prefix `[Video: … | Nhóm: … | Chủ đề: … | Thời gian: …]`).
- Giữ field legacy `text` / `source_text` để tương thích ngược.

### 3. Query preprocessing
- **Rule-based `QUERY_NORMALIZER`** trong `config.py` (VD: `od`→`OneDrive`, `2fa`→`xác thực đa lớp`, `share`→`chia sẻ`...). Không tốn API.
- **Haiku query rewrite** trả về JSON `{rewritten_query, keywords, product}`; `keywords` đẩy vào keyword boost, `product` kích hoạt `PRODUCT_BOOST` trong retriever.

### 4. LLM reranking
- Gọi Claude Haiku chấm điểm 0..1 cho top-K trước, re-sort rồi cắt còn `RERANK_TOP_K = 5`.
- Bật/tắt bằng `ENABLE_RERANKING` trong `config.py`.
- Lỗi API → **silent fallback** về điểm hybrid ban đầu.

### 5. Response quality
- System prompt mới: bắt buộc trích dẫn `[Nguồn: …] tại [timestamp]`, fallback message "Tôi chưa có tài liệu hướng dẫn về vấn đề này.", dạng các bước đánh số.
- `MAX_TOKENS`: 1024 → **2048**.
- Confidence indicator tự động inject vào system prompt.

### 6. Multi-source pipeline (Documents / Excel / Images)
- **Documents:** `docx` (python-docx) giữ heading hierarchy, `pdf` (pdfplumber) với phát hiện header/footer lặp, `txt`. Chunk theo section; bảng giữ nguyên một chunk.
- **Excel:** auto Strategy A (>20 dòng → 10 dòng/chunk, overlap 2) hoặc Strategy B (bảng nhỏ → 1 chunk mô tả). Chuẩn hóa NFC, date `DD/MM/YYYY`.
- **Images:** Claude Haiku vision với prompt tiếng Việt → JSON có `product/topic/step_number/description/extracted_text/ui_elements`. **Cache bắt buộc** tại `data/processed/image_descriptions.json` (skip nếu đã có), batch 5 ảnh/lần + sleep 1s.

### 7. Unified build
- `scripts/build_vectors.py` viết lại hoàn toàn: load videos + docs + excel + images, merge, embed bằng BGE-M3, ghi `vectors.json` + `build_manifest.json` (sha256 nguồn) + `chunks.jsonl`.
- Cờ `--full` để đi qua tất cả các nguồn; mặc định chỉ build videos.
- Các loader tùy chọn skip mềm khi thiếu thư viện.

### 8. API / Web UI
- `ChatResponse` bổ sung `confidence`, `rewritten_query`; `SourceInfo` bổ sung `source_type`, `rerank_score`.
- Web UI:
  - 6 suggestion chips M365 mới.
  - **Source cards** dạng `[VIDEO]/[DOC]/[EXCEL]/[IMAGE]` + tên nguồn + timestamp + score %.
  - **Confidence badge** (high/medium/low).
  - **Copy button** trên mỗi câu trả lời bot.
  - Typing indicator giữ nguyên, clean lại.

### 9. Evaluation
- `scripts/eval_retrieval.py`: 10 test cases keyed theo `videos.json` thật, in Hit@1 / Hit@3 / MRR + breakdown top-3 mỗi câu.

### 10. Latency optimization (v2)

Cắt perceived latency từ ~10s xuống ~1s first-token mà không đổi signature của `RAGChain.query`, `Retriever.search`, `ClaudeClient.generate`.

**Before vs After (đo thực tế):**

| Bước | Before | After |
| --- | --- | --- |
| Prep (normalize → retrieve → rerank) | ~3.5s | **0.128s** |
| — rewrite_query (Haiku) | ~1.5s | skipped (gate) |
| — rerank (Haiku) | ~1.5s | skipped (gate) |
| — boost_rank loop | ~0.2s | 0.000s (precompute) |
| — encode_query (BGE-M3) | ~0.3s | 0.113s |
| First token hiển thị trên UI | ~10s | **~1s** (streaming) |
| Full answer complete | ~10s | ~9.5s (bound by Sonnet throughput) |

**Các thay đổi:**

- **Streaming**: `ClaudeClient.generate_stream()` dùng `anthropic.messages.stream()`, `RAGChain.query_stream()` yield `meta → delta* → done`, `POST /chat/stream` trả `StreamingResponse` SSE. `/chat` cũ giữ nguyên.
- **Rewrite gate** (`rag/chain.py`): chỉ gọi Haiku rewrite khi có `history` hoặc `normalized.split() < 4`. Query đơn giản không bị phí 1.5s.
- **Rerank gate** (`rag/chain.py`): skip Haiku rerank khi `top_score >= RERANK_SKIP_THRESHOLD` (mặc định 0.7) hoặc `len(chunks) < 3`. Câu "high confidence" không bị phí 1.5s.
- **Precompute keyword sets** (`rag/retriever.py`): `_chunk_keywords` và `_chunk_product_haystack` tính một lần trong `Retriever.__init__`, hot path trong `search()` không còn per-chunk tokenization.
- **`MAX_TOKENS` 2048 → 1024**: đủ cho câu trả lời M365, không cắt ngang trong test.
- **Timing instrumentation**: `[TIMING] <step>: X.XXXs` ở `rag/chain.py`, `rag/retriever.py` — tiện profile khi tuning thêm.
- **Web UI** (`web/app.js`): `sendMessage` parser SSE, hiển thị sources ngay khi nhận `meta`, append text dần theo `delta`.

---

## Config mới (`config.py`)

| Key                        | Giá trị                           | Ý nghĩa                                    |
| -------------------------- | --------------------------------- | ------------------------------------------ |
| `EMBEDDING_MODEL`          | `BAAI/bge-m3`                     | Model embedding                            |
| `EMBEDDING_DIM`            | `1024`                            | Kích thước vector                          |
| `ENABLE_RERANKING`         | `True`                            | Bật LLM rerank                             |
| `RERANK_TOP_K`             | `5`                               | Số chunk giữ lại sau rerank                |
| `RERANK_SKIP_THRESHOLD`    | `0.7`                             | Bỏ rerank khi top score >= ngưỡng này      |
| `ENABLE_QUERY_REWRITE`     | `True`                            | Bật Haiku rewrite                          |
| `CLAUDE_MODEL`             | `claude-sonnet-4-20250514`        | Model sinh câu trả lời                     |
| `CLAUDE_HAIKU_MODEL`       | `claude-haiku-4-5-20251001`       | Model rerank / rewrite / vision            |
| `MAX_TOKENS`               | `1024`                            | Max tokens khi sinh câu trả lời            |
| `RAW_DOCS_DIR`             | `data/raw/docs`                   | Nguồn tài liệu                             |
| `RAW_EXCEL_DIR`            | `data/raw/excel`                  | Nguồn Excel                                |
| `RAW_IMAGES_DIR`           | `data/raw/images`                 | Nguồn ảnh                                  |
| `IMAGE_DESCRIPTIONS_PATH`  | `data/processed/image_descriptions.json` | Cache Claude vision            |
| `BUILD_MANIFEST_PATH`      | `data/processed/build_manifest.json`     | Manifest pipeline              |
| `QUERY_NORMALIZER`         | dict                              | Map từ viết tắt / lỗi gõ → chuẩn           |

Tham số retriever (`rag/retriever.py`):

| Tham số               | Giá trị | Mô tả                                    |
| ---------------------- | ------- | ----------------------------------------- |
| `KEYWORD_BOOST`        | 0.05    | Bonus mỗi keyword trùng (tối đa 3 từ)    |
| `PRODUCT_BOOST`        | 0.04    | Bonus khi khớp `product_hint` từ rewrite |
| `SAME_VIDEO_BOOST`     | 0.06    | Bonus khi nhiều chunk cùng nguồn         |
| `MAX_CHUNKS_PER_VIDEO` | 3       | Giới hạn chunk/nguồn                      |
| `TOP_K`                | 7       | Số chunk lấy ban đầu                      |
| `MIN_SIMILARITY`       | 0.25    | Ngưỡng tối thiểu                          |

---

## Cách chạy

### 1. Cài đặt

```bash
pip install -r requirements.txt
```

Các thư viện mới được thêm: `torch`, `python-docx`, `pdfplumber`, `openpyxl`, `pandas`, `Pillow`.

### 2. Cấu hình `.env`

```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### 3. Chuẩn bị dữ liệu (tùy chọn cho đa nguồn)

```
data/raw/docs/    ← .docx / .pdf / .txt
data/raw/excel/   ← .xlsx / .xls / .csv
data/raw/images/  ← .png / .jpg / .jpeg / .webp
```

### 4. Build vector cache

```bash
# Chỉ videos
python scripts/build_vectors.py

# Đa nguồn (videos + docs + excel + images)
python scripts/build_vectors.py --full
```

> Lần đầu chạy BGE-M3 sẽ tải ~2GB model weights. Lần đầu `--full` sẽ gọi Claude vision cho mọi ảnh (kết quả được cache, lần sau miễn phí).

### 5. Đánh giá chất lượng retrieval

```bash
python scripts/eval_retrieval.py
```

In Hit@1, Hit@3, MRR + breakdown top-3 của mỗi câu hỏi test.

### 6. Chạy server API + Web UI

```bash
python -m api.server
# http://localhost:8000/                 ← Web UI (tự dùng /chat/stream)
# POST http://localhost:8000/chat        ← API non-stream (JSON)
# POST http://localhost:8000/chat/stream ← API streaming (SSE)
```

Test nhanh streaming bằng curl:

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"làm sao bật xác thực 2 lớp","session_id":"t1"}'
```

### 7. Chat CLI

```bash
python scripts/chat_cli.py
```

---

## Tech Stack

| Thành phần      | Công nghệ                                                |
| --------------- | --------------------------------------------------------- |
| LLM (answer)    | Claude Sonnet 4 — `claude-sonnet-4-20250514`              |
| LLM (rerank / rewrite / vision) | Claude Haiku — `claude-haiku-4-5-20251001` |
| Embedding       | `BAAI/bge-m3` (1024-dim, multilingual)                    |
| Vector Store    | JSON file + NumPy cosine (không dùng DB)                  |
| Document parse  | python-docx, pdfplumber, openpyxl, pandas                 |
| Image parse     | Pillow + Claude vision                                    |
| API Framework   | FastAPI + Uvicorn                                         |
| Frontend        | HTML / CSS / JS vanilla                                   |
| Validation      | Pydantic v2                                               |
| Config          | python-dotenv                                             |
