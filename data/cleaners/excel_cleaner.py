"""Excel cell-level cleaning: whitespace, NFC, date formatting, empty rows."""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime

from data.loaders.excel_loader import LoadedSheet

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
)


def _clean_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    text = unicodedata.normalize("NFC", text)
    # Try to normalize obvious date strings.
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            continue
    text = re.sub(r"\s+", " ", text)
    return text


def clean_sheet(sheet: LoadedSheet) -> LoadedSheet:
    sheet.headers = [_clean_cell(h) for h in sheet.headers]
    cleaned_rows: list[list[str]] = []
    prev_row: list[str] | None = None
    for row in sheet.rows:
        cleaned = [_clean_cell(c) for c in row]
        if not any(cleaned):
            continue
        # Merge rows that look like continuations of previous (leading blanks
        # in the key column).
        if prev_row is not None and cleaned and not cleaned[0]:
            prev_row[:] = [
                (a + " " + b).strip() if b else a for a, b in zip(prev_row, cleaned)
            ]
            continue
        cleaned_rows.append(cleaned)
        prev_row = cleaned_rows[-1]
    sheet.rows = cleaned_rows
    sheet.total_rows = len(cleaned_rows)
    return sheet
