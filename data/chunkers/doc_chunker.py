"""Section-aware chunking for documents."""
from __future__ import annotations

from dataclasses import dataclass

from data.loaders.doc_loader import DocBlock, LoadedDoc

MAX_SECTION_CHARS = 600
CHILD_CHUNK_CHARS = 300
CHILD_OVERLAP_CHARS = 50


@dataclass
class _Section:
    heading: str
    page_number: int | None
    body: list[str]
    tables: list[tuple[str, int | None]]


def _group_sections(doc: LoadedDoc) -> list[_Section]:
    sections: list[_Section] = []
    current = _Section(heading="", page_number=None, body=[], tables=[])
    for block in doc.blocks:
        if block.kind == "heading":
            if current.body or current.tables:
                sections.append(current)
            current = _Section(
                heading=block.text,
                page_number=block.page_number,
                body=[],
                tables=[],
            )
        elif block.kind == "table":
            current.tables.append((block.text, block.page_number))
        else:
            if current.page_number is None:
                current.page_number = block.page_number
            current.body.append(block.text)
    if current.body or current.tables:
        sections.append(current)
    return sections


def _window(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    out: list[str] = []
    start = 0
    step = max(1, size - overlap)
    while start < len(text):
        out.append(text[start : start + size])
        start += step
    return out


def _context_prefix(title: str, section: str, page: int | None) -> str:
    parts = [f"Tài liệu: {title}"]
    if section:
        parts.append(f"Mục: {section}")
    if page:
        parts.append(f"Trang: {page}")
    return "[" + " | ".join(parts) + "]"


def chunk_document(doc: LoadedDoc) -> list[dict]:
    sections = _group_sections(doc)
    chunks: list[dict] = []

    for section in sections:
        body_text = "\n".join(section.body).strip()
        if body_text:
            pieces = (
                [body_text]
                if len(body_text) <= MAX_SECTION_CHARS
                else _window(body_text, CHILD_CHUNK_CHARS, CHILD_OVERLAP_CHARS)
            )
            for piece in pieces:
                prefix = _context_prefix(
                    doc.title, section.heading, section.page_number
                )
                chunks.append(
                    {
                        "source_type": "document",
                        "file_name": doc.file_name,
                        "title": doc.title,
                        "section": section.heading,
                        "page_number": section.page_number,
                        "text_raw": piece,
                        "text_embed": f"{prefix}\n{piece}",
                        "chunk_type": "doc_section",
                        # Shared/retriever-compat fields
                        "video_name": doc.file_name,
                        "chu_de": doc.title,
                        "nhom": section.heading,
                        "start_time": "",
                        "end_time": "",
                        "timestamp": "",
                        "links": "",
                    }
                )

        for table_text, page in section.tables:
            prefix = _context_prefix(doc.title, section.heading, page)
            chunks.append(
                {
                    "source_type": "document",
                    "file_name": doc.file_name,
                    "title": doc.title,
                    "section": section.heading,
                    "page_number": page,
                    "text_raw": table_text,
                    "text_embed": f"{prefix}\n{table_text}",
                    "chunk_type": "doc_table",
                    "video_name": doc.file_name,
                    "chu_de": doc.title,
                    "nhom": section.heading,
                    "start_time": "",
                    "end_time": "",
                    "timestamp": "",
                    "links": "",
                }
            )

    total = len(chunks)
    for i, c in enumerate(chunks):
        c["chunk_index"] = i
        c["total_chunks"] = total
    return chunks
