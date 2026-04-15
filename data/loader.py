from __future__ import annotations
import json
from pathlib import Path


def load_videos(path: str | Path) -> list[dict]:
    """Load videos.json and return list of video dicts with valid transcripts."""
    with open(path, "r", encoding="utf-8") as f:
        videos = json.load(f)

    valid = []
    for v in videos:
        if v.get("transcript"):
            valid.append(v)
    return valid
