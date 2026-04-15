"""Turn vision descriptions into embeddable chunk dicts."""
from __future__ import annotations


def chunk_image(img: dict, description: dict) -> dict:
    product = description.get("product") or img["parsed_meta"].get("product", "Other")
    topic = description.get("topic") or img["parsed_meta"].get("topic", "")
    step = description.get("step_number") or img["parsed_meta"].get("step")
    desc_text = description.get("description", "")
    extracted = description.get("extracted_text", "")
    ui_elements = description.get("ui_elements", [])
    ui_text = ", ".join(ui_elements) if isinstance(ui_elements, list) else str(ui_elements)

    step_str = f"Bước {step}" if step else ""
    text_raw_lines = [f"[Ảnh hướng dẫn] {topic}{' - ' + step_str if step_str else ''}"]
    if desc_text:
        text_raw_lines.append(f"Mô tả: {desc_text}")
    if extracted:
        text_raw_lines.append(f"Văn bản trong ảnh: {extracted}")
    if ui_text:
        text_raw_lines.append(f"Các thành phần UI: {ui_text}")
    text_raw = "\n".join(text_raw_lines)

    header_parts = [f"Ảnh: {img['file_name']}", f"Sản phẩm: {product}"]
    if topic:
        header_parts.append(f"Chủ đề: {topic}")
    if step:
        header_parts.append(f"Bước: {step}")
    prefix = "[" + " | ".join(header_parts) + "]"

    return {
        "source_type": "image",
        "file_name": img["file_name"],
        "product": product,
        "topic": topic,
        "step_number": step,
        "text_raw": text_raw,
        "text_embed": f"{prefix}\n{text_raw}",
        "chunk_type": "image_description",
        # retriever-compat fields
        "video_name": img["file_name"],
        "chu_de": topic or img["file_name"],
        "nhom": product,
        "start_time": "",
        "end_time": "",
        "timestamp": "",
        "links": "",
    }
