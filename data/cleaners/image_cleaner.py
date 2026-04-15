"""Describe images with Claude Haiku vision and cache results."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import anthropic

import config

VISION_PROMPT = (
    "Bạn đang xem ảnh chụp màn hình hướng dẫn sử dụng Microsoft 365.\n"
    "Hãy mô tả chi tiết:\n"
    "1. Đây là hướng dẫn về tính năng gì? (Teams/Outlook/OneDrive/Authenticator/Other)\n"
    "2. Các bước hoặc nội dung hiển thị trong ảnh là gì?\n"
    "3. Có văn bản nào trong ảnh không? Hãy trích xuất nguyên văn.\n"
    "4. Đây là bước thứ mấy trong quy trình (nếu có)?\n\n"
    "Trả về JSON với các trường: product, topic, step_number, description, "
    "extracted_text, ui_elements (mảng chuỗi)."
)

BATCH_SIZE = 5
BATCH_SLEEP_SECONDS = 1


def _load_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return {}


def describe_images(images: list[dict], cache_path: Path) -> dict[str, dict]:
    cache = _load_cache(cache_path)
    pending = [img for img in images if img["file_name"] not in cache]
    if not pending:
        return cache

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start : start + BATCH_SIZE]
        for img in batch:
            try:
                response = client.messages.create(
                    model=config.CLAUDE_HAIKU_MODEL,
                    max_tokens=800,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": img["media_type"],
                                        "data": img["base64"],
                                    },
                                },
                                {"type": "text", "text": VISION_PROMPT},
                            ],
                        }
                    ],
                )
                text = response.content[0].text
                parsed = _parse_json(text)
                if parsed:
                    cache[img["file_name"]] = parsed
                    _save_cache(cache_path, cache)
            except Exception as exc:
                print(f"[image_cleaner] vision failed on {img['file_name']}: {exc}")
        if start + BATCH_SIZE < len(pending):
            time.sleep(BATCH_SLEEP_SECONDS)

    _save_cache(cache_path, cache)
    return cache
