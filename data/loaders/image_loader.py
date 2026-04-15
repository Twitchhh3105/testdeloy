"""Load image files for multimodal processing."""
from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Iterator

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
MIN_PIXELS = 100


def _parse_filename(name: str) -> dict:
    stem = Path(name).stem
    tokens = re.split(r"[_\-]+", stem)
    meta: dict = {}
    known_products = {"teams", "outlook", "onedrive", "authenticator", "sharepoint"}
    topic_parts: list[str] = []
    for tok in tokens:
        lower = tok.lower()
        if lower in known_products:
            meta["product"] = lower.capitalize() if lower != "onedrive" else "OneDrive"
        elif lower.startswith("step") and lower[4:].isdigit():
            meta["step"] = int(lower[4:])
        else:
            topic_parts.append(tok)
    if topic_parts:
        meta["topic"] = " ".join(topic_parts)
    return meta


def _is_large_enough(path: Path) -> bool:
    try:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
            return w >= MIN_PIXELS and h >= MIN_PIXELS
    except Exception:
        return True


def load_image(path: Path) -> dict | None:
    if path.suffix.lower() not in SUPPORTED_EXTS:
        return None
    if not _is_large_enough(path):
        return None
    raw = path.read_bytes()
    return {
        "source_type": "image",
        "file_name": path.name,
        "file_path": str(path),
        "base64": base64.standard_b64encode(raw).decode("ascii"),
        "media_type": MEDIA_TYPES[path.suffix.lower()],
        "parsed_meta": _parse_filename(path.name),
    }


def load_images(root: Path) -> Iterator[dict]:
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        img = load_image(path)
        if img:
            yield img
