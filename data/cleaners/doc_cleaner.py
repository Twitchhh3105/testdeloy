"""Document-specific cleaning: boilerplate removal, bullets, hyphenation."""
from __future__ import annotations

import re
import unicodedata

from data.loaders.doc_loader import DocBlock, LoadedDoc


_BOILERPLATE_PATTERNS = [
    re.compile(r"^\s*trang\s*\d+\s*(/\s*\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*page\s*\d+\s*(of\s*\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*confidential\s*$", re.IGNORECASE),
]

_BULLET_RE = re.compile(r"^\s*(?:[-*•●◦▪–]|\d+[.)])\s+")
_HYPHEN_BREAK_RE = re.compile(r"(\w)-\s+(\w)")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")


def _is_boilerplate(text: str) -> bool:
    return any(p.match(text) for p in _BOILERPLATE_PATTERNS)


def _normalize_bullets(text: str) -> str:
    return _BULLET_RE.sub("- ", text)


def _merge_hyphenation(text: str) -> str:
    return _HYPHEN_BREAK_RE.sub(lambda m: m.group(1) + " " + m.group(2), text)


def _clean_block_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _merge_hyphenation(text)
    text = _normalize_bullets(text)
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    return text.strip()


def clean_document(doc: LoadedDoc) -> LoadedDoc:
    cleaned_blocks: list[DocBlock] = []
    for block in doc.blocks:
        if _is_boilerplate(block.text):
            continue
        text = _clean_block_text(block.text)
        if not text:
            continue
        cleaned_blocks.append(
            DocBlock(
                kind=block.kind,
                level=block.level,
                text=text,
                page_number=block.page_number,
            )
        )
    doc.blocks = cleaned_blocks
    return doc
