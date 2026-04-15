"""Retrieval evaluation: Hit@1, Hit@3, MRR over hardcoded test cases.

Usage:
    python scripts/eval_retrieval.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from embeddings import EmbeddingEncoder
from rag.retriever import Retriever


TEST_CASES = [
    {
        "question": "Hướng dẫn cài Authenticator để xác thực đăng nhập",
        "expected": "Authenticator.mp4",
    },
    {
        "question": "Cách chat và trao đổi công việc trên Teams",
        "expected": "Chat và trao đổi công việc.mp4",
    },
    {
        "question": "Đồng bộ dữ liệu OneDrive về máy tính cá nhân",
        "expected": "Đồng bộ dữ liệu từ cloud về máy tính cá nhân.mp4",
    },
    {
        "question": "Gom nhóm và phân loại email trong Outlook",
        "expected": "Gom nhóm phân loại email.mp4",
    },
    {
        "question": "Sử dụng hộp thư chung cho nhóm",
        "expected": "Hướng dẫn sử dụng Hộp thư chung (email chung, email nhóm).mp4",
    },
    {
        "question": "Lưu trữ tài liệu cá nhân và chia sẻ file OneDrive",
        "expected": "Lưu trữ tài liệu cá nhân, cách tạo folder, upload file và phân loại tài liệu, chia sẻ tài liệu.mp4",
    },
    {
        "question": "Quản lý file chia sẻ trên Teams và SharePoint",
        "expected": "Quản lý file và thông tin được chia sẻ trên Teams và Sharepoint.mp4",
    },
    {
        "question": "Đặt lịch họp và gọi điện trong Teams",
        "expected": "Sử dụng lịch và cuộc gọi trong Teams.mp4",
    },
    {
        "question": "Cách tạo chữ ký email Outlook",
        "expected": "Tạo chữ ký.mp4",
    },
    {
        "question": "Tổng quan các tính năng của Microsoft Teams",
        "expected": "Tổng quan về Teams.mp4",
    },
]


def main() -> None:
    print("=== Retrieval Evaluation ===\n")
    encoder = EmbeddingEncoder(config.EMBEDDING_MODEL)
    cache_data = EmbeddingEncoder.load_cache(config.VECTOR_CACHE_PATH)
    retriever = Retriever(cache_data, encoder)

    hit1 = 0
    hit3 = 0
    reciprocal_sum = 0.0

    for i, case in enumerate(TEST_CASES, start=1):
        q = case["question"]
        expected = case["expected"]
        results = retriever.search(q, top_k=5, min_similarity=0.0)
        videos = [r.get("video_name") or r.get("file_name", "") for r in results]

        rank = None
        for idx, v in enumerate(videos, start=1):
            if v == expected:
                rank = idx
                break

        if rank == 1:
            hit1 += 1
        if rank and rank <= 3:
            hit3 += 1
        if rank:
            reciprocal_sum += 1.0 / rank

        status = f"rank {rank}" if rank else "MISS"
        print(f"[{i:2d}] {status:8s} | Q: {q}")
        print(f"       expected: {expected}")
        for j, v in enumerate(videos[:3], start=1):
            marker = "✓" if v == expected else " "
            print(f"       {marker} top{j}: {v}")
        print()

    n = len(TEST_CASES)
    print("=" * 60)
    print(f"Hit@1: {hit1}/{n} ({hit1 / n * 100:.1f}%)")
    print(f"Hit@3: {hit3}/{n} ({hit3 / n * 100:.1f}%)")
    print(f"MRR:   {reciprocal_sum / n:.3f}")


if __name__ == "__main__":
    main()
