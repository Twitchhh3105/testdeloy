from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

from .cleaner import clean_transcript, normalize_text


@dataclass
class Chunk:
    chunk_id: str
    video_name: str
    nhom: str
    chu_de: str
    start_time: str
    end_time: str
    text_raw: str            # shown to user / LLM context
    text_embed: str          # used for embedding (with context prefix)
    chunk_type: str          # "transcript" or "summary"
    timestamp: str = ""
    chunk_index: int = 0
    total_chunks: int = 0
    links: str = ""
    source_type: str = "video"

    # Back-compat aliases (read-only via property-like access in dict form).
    @property
    def text(self) -> str:
        return self.text_embed

    @property
    def source_text(self) -> str:
        return self.text_raw

    def to_dict(self) -> dict:
        d = asdict(self)
        # Keep legacy keys for any downstream consumer that still reads them.
        d["text"] = self.text_embed
        d["source_text"] = self.text_raw
        return d


def _parse_timestamp_segments(transcript: str) -> list[tuple[str, str]]:
    """Split transcript into (timestamp, text) segments."""
    pattern = r"(\d{2}:\d{2})\s+"
    parts = re.split(pattern, transcript)

    segments: list[tuple[str, str]] = []
    i = 1
    while i < len(parts) - 1:
        ts = parts[i]
        text = parts[i + 1].strip()
        if text:
            segments.append((ts, text))
        i += 2
    return segments


def _merge_segments(
    segments: list[tuple[str, str]], max_chars: int, overlap_chars: int
) -> list[tuple[str, str, str]]:
    if not segments:
        return []

    chunks: list[tuple[str, str, str]] = []
    current_texts: list[str] = []
    current_start = segments[0][0]
    current_len = 0

    for ts, text in segments:
        text_len = len(text)
        if current_len + text_len > max_chars and current_texts:
            merged = " ".join(current_texts)
            end_time = ts
            chunks.append((current_start, end_time, merged))
            if overlap_chars > 0 and current_texts:
                last = current_texts[-1]
                current_texts = [last] if len(last) <= overlap_chars else []
                current_len = len(last) if current_texts else 0
            else:
                current_texts = []
                current_len = 0
            current_start = ts

        current_texts.append(text)
        current_len += text_len

    if current_texts:
        merged = " ".join(current_texts)
        end_time = segments[-1][0]
        chunks.append((current_start, end_time, merged))

    return chunks


def _make_chunk_id(video_name: str, start: str, end: str, suffix: str = "") -> str:
    base = video_name.replace(".mp4", "").replace(".mov", "")
    base = re.sub(r"[^\w]", "_", base)[:40]
    cid = f"{base}_{start}_{end}"
    if suffix:
        cid += f"_{suffix}"
    return cid


def _build_context_prefix(name: str, nhom: str, chu_de: str, timestamp: str) -> str:
    parts = [f"Video: {name}"]
    if nhom:
        parts.append(f"Nhóm: {nhom}")
    if chu_de:
        parts.append(f"Chủ đề: {chu_de}")
    if timestamp:
        parts.append(f"Thời gian: {timestamp}")
    return "[" + " | ".join(parts) + "]"


def chunk_single_video(video: dict, max_chars: int, overlap_chars: int) -> list[Chunk]:
    name = video["name"]
    nhom = video.get("nhom") or ""
    chu_de = video.get("chu_de") or ""
    noi_dung = video.get("noi_dung") or ""
    transcript = video.get("transcript") or ""
    links = video.get("links") or ""

    produced: list[Chunk] = []

    # Summary chunk (metadata)
    summary_parts = [p for p in [nhom, chu_de, noi_dung] if p]
    if summary_parts:
        summary_raw = f"Video: {name}. " + " | ".join(summary_parts)
        summary_raw = normalize_text(summary_raw)
        prefix = _build_context_prefix(name, nhom, chu_de, "")
        produced.append(
            Chunk(
                chunk_id=_make_chunk_id(name, "meta", "summary"),
                video_name=name,
                nhom=nhom,
                chu_de=chu_de,
                start_time="",
                end_time="",
                text_raw=summary_raw,
                text_embed=f"{prefix}\n{summary_raw}",
                chunk_type="summary",
                timestamp="",
                links=links,
            )
        )

    cleaned = clean_transcript(transcript)
    if not cleaned:
        _finalize_indices(produced)
        return produced

    segments = _parse_timestamp_segments(transcript)
    if not segments:
        prefix = _build_context_prefix(name, nhom, chu_de, "00:00")
        produced.append(
            Chunk(
                chunk_id=_make_chunk_id(name, "00_00", "end"),
                video_name=name,
                nhom=nhom,
                chu_de=chu_de,
                start_time="00:00",
                end_time="end",
                text_raw=cleaned,
                text_embed=f"{prefix}\n{cleaned}",
                chunk_type="transcript",
                timestamp="00:00",
                links=links,
            )
        )
        _finalize_indices(produced)
        return produced

    merged = _merge_segments(segments, max_chars, overlap_chars)
    for start_time, end_time, text in merged:
        clean_text = clean_transcript(text)
        prefix = _build_context_prefix(name, nhom, chu_de, start_time)
        produced.append(
            Chunk(
                chunk_id=_make_chunk_id(
                    name,
                    start_time.replace(":", "_"),
                    end_time.replace(":", "_"),
                ),
                video_name=name,
                nhom=nhom,
                chu_de=chu_de,
                start_time=start_time,
                end_time=end_time,
                text_raw=clean_text,
                text_embed=f"{prefix}\n{clean_text}",
                chunk_type="transcript",
                timestamp=start_time,
                links=links,
            )
        )

    _finalize_indices(produced)
    return produced


def _finalize_indices(chunks: list[Chunk]) -> None:
    total = len(chunks)
    for i, c in enumerate(chunks):
        c.chunk_index = i
        c.total_chunks = total


def chunk_videos(
    videos: list[dict], max_chars: int = 500, overlap_chars: int = 50
) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for video in videos:
        all_chunks.extend(chunk_single_video(video, max_chars, overlap_chars))
    return all_chunks
