"""Chunk Excel sheets: reference (Strategy A) vs report (Strategy B)."""
from __future__ import annotations

from data.loaders.excel_loader import LoadedSheet

ROWS_PER_CHUNK = 10
ROW_OVERLAP = 2
REFERENCE_THRESHOLD = 20


def _row_to_line(headers: list[str], row: list[str]) -> str:
    pairs = []
    for h, v in zip(headers, row):
        if not v:
            continue
        pairs.append(f"{h}: {v}" if h else v)
    return " | ".join(pairs)


def _context_prefix(file_name: str, sheet_name: str, row_range: str) -> str:
    return f"[Excel: {file_name} | Sheet: {sheet_name} | Dòng: {row_range}]"


def _chunk_reference(sheet: LoadedSheet) -> list[dict]:
    chunks: list[dict] = []
    total = sheet.total_rows
    step = ROWS_PER_CHUNK - ROW_OVERLAP
    i = 0
    while i < total:
        end = min(i + ROWS_PER_CHUNK, total)
        rows = sheet.rows[i:end]
        body_lines = [
            f"- {_row_to_line(sheet.headers, r)}" for r in rows
        ]
        row_range = f"{i + 1}-{end}"
        header_line = (
            f"Danh sách {sheet.sheet_name} (dòng {row_range}):"
        )
        text_raw = header_line + "\n" + "\n".join(body_lines)
        prefix = _context_prefix(sheet.file_name, sheet.sheet_name, row_range)
        chunks.append(
            {
                "source_type": "excel",
                "file_name": sheet.file_name,
                "sheet_name": sheet.sheet_name,
                "row_range": row_range,
                "text_raw": text_raw,
                "text_embed": f"{prefix}\n{text_raw}",
                "chunk_type": "excel_rows",
                "video_name": sheet.file_name,
                "chu_de": sheet.sheet_name,
                "nhom": "Excel",
                "start_time": "",
                "end_time": "",
                "timestamp": "",
                "links": "",
            }
        )
        if end >= total:
            break
        i += step
    return chunks


def _chunk_summary(sheet: LoadedSheet) -> list[dict]:
    lines = [f"Bảng {sheet.sheet_name}:"]
    for row in sheet.rows:
        line = _row_to_line(sheet.headers, row)
        if line:
            lines.append(f"- {line}")
    text_raw = "\n".join(lines)
    row_range = f"1-{sheet.total_rows}"
    prefix = _context_prefix(sheet.file_name, sheet.sheet_name, row_range)
    return [
        {
            "source_type": "excel",
            "file_name": sheet.file_name,
            "sheet_name": sheet.sheet_name,
            "row_range": row_range,
            "text_raw": text_raw,
            "text_embed": f"{prefix}\n{text_raw}",
            "chunk_type": "excel_summary",
            "video_name": sheet.file_name,
            "chu_de": sheet.sheet_name,
            "nhom": "Excel",
            "start_time": "",
            "end_time": "",
            "timestamp": "",
            "links": "",
        }
    ]


def chunk_sheet(sheet: LoadedSheet) -> list[dict]:
    if sheet.total_rows == 0:
        return []
    chunks = (
        _chunk_reference(sheet)
        if sheet.total_rows > REFERENCE_THRESHOLD
        else _chunk_summary(sheet)
    )
    total = len(chunks)
    for i, c in enumerate(chunks):
        c["chunk_index"] = i
        c["total_chunks"] = total
    return chunks
