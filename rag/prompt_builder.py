SYSTEM_PROMPT = """Bạn là trợ lý hỗ trợ kỹ thuật Microsoft 365 cho người dùng tiếng Việt.
Chỉ trả lời dựa trên nội dung tài liệu (video hướng dẫn, tài liệu văn bản, bảng tính, ảnh chụp màn hình) được cung cấp.
Trình bày câu trả lời theo dạng các bước đánh số nếu là hướng dẫn thực hiện.
Luôn trích dẫn nguồn ở cuối câu trả lời theo định dạng: [Nguồn: Tên] tại [timestamp nếu có].
Nếu không tìm thấy thông tin trong context, nói rõ: "Tôi chưa có tài liệu hướng dẫn về vấn đề này."
KHÔNG đính kèm link URL trong câu trả lời — hệ thống sẽ tự động hiển thị link ở phần nguồn tham khảo.
Trả lời bằng tiếng Việt, rõ ràng và dễ hiểu.
"""


def _timestamp_to_seconds(ts: str) -> int:
    """Convert MM:SS timestamp to total seconds."""
    parts = ts.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0


def _build_video_link(base_url: str, start_time: str) -> str:
    """Build a YouTube URL with timestamp parameter."""
    if not base_url:
        return ""
    seconds = _timestamp_to_seconds(start_time) if start_time else 0
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}t={seconds}s"


def build_context_block(chunks: list[dict]) -> str:
    """Format retrieved chunks into a context block for Claude."""
    if not chunks:
        return "Không tìm thấy thông tin liên quan trong cơ sở dữ liệu video."

    blocks = []
    for i, chunk in enumerate(chunks, 1):
        time_info = ""
        if chunk.get("start_time") and chunk.get("end_time"):
            time_info = f" | Thời gian: {chunk['start_time']}-{chunk['end_time']}"

        link_info = ""
        if chunk.get("links"):
            video_link = _build_video_link(chunk["links"], chunk.get("start_time", ""))
            link_info = f" | Link: {video_link}"

        header = (
            f"[Nguồn {i}: {chunk['video_name']} | "
            f"Nhóm: {chunk.get('nhom', 'N/A')} | "
            f"Chủ đề: {chunk.get('chu_de', 'N/A')}{time_info}{link_info}]"
        )
        blocks.append(f"{header}\n{chunk.get('text_raw') or chunk.get('text', '')}")

    return "=== CONTEXT TỪ VIDEO HƯỚNG DẪN ===\n\n" + "\n\n---\n\n".join(blocks)


def format_sources(chunks: list[dict]) -> list[dict]:
    """Extract source citations from chunks (multi-source aware)."""
    seen = set()
    sources = []
    for c in chunks:
        name = c.get("video_name") or c.get("file_name", "")
        key = (name, c.get("start_time", ""), c.get("chunk_index", 0))
        if key in seen:
            continue
        seen.add(key)
        video_link = _build_video_link(
            c.get("links", ""), c.get("start_time", "")
        )
        src = {
            "video": name,
            "nhom": c.get("nhom", "") or c.get("section", ""),
            "chu_de": c.get("chu_de", "") or c.get("topic", "") or c.get("title", ""),
            "time": c.get("start_time", "") or c.get("timestamp", ""),
            "score": round(c.get("score", 0), 3),
            "link": video_link,
            "source_type": c.get("source_type", "video"),
        }
        if "rerank_score" in c:
            src["rerank_score"] = round(float(c["rerank_score"]), 3)
        sources.append(src)
    return sources
