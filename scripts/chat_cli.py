"""Interactive CLI chat for local testing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag import RAGChain


def main():
    print("=== M365 Video Assistant (CLI) ===")
    print("Đang tải mô hình... ", end="", flush=True)

    chain = RAGChain()
    print("OK!\n")

    print("Hỏi bất kỳ câu hỏi nào về Microsoft 365.")
    print("Gõ 'quit' hoặc 'exit' để thoát.\n")

    history: list[dict] = []

    while True:
        try:
            question = input("Bạn: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTạm biệt!")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "/quit", "/exit"):
            print("Tạm biệt!")
            break

        result = chain.query(question, history=history)

        # Update local history
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": result["answer"]})

        # Keep history manageable
        if len(history) > 20:
            history = history[-20:]

        # Display answer
        print(f"\nTrợ lý: {result['answer']}\n")

        # Display sources
        if result["sources"]:
            print("  📎 Nguồn tham khảo:")
            for s in result["sources"]:
                time_str = f" ({s['time']})" if s["time"] else ""
                link_str = f"\n      🔗 {s['link']}" if s.get("link") else ""
                print(f"    - {s['video']}{time_str} [score: {s['score']}]{link_str}")
            print()


if __name__ == "__main__":
    main()
