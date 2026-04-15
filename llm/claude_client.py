from __future__ import annotations

from typing import Iterator

import anthropic


class ClaudeClient:
    def __init__(self, api_key: str, model: str, max_tokens: int = 2048):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def generate(
        self,
        system_prompt: str,
        context_block: str,
        messages: list[dict],
    ) -> str:
        """Call Claude with prompt caching on system + context."""
        system = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if context_block:
            system.append(
                {
                    "type": "text",
                    "text": context_block,
                    "cache_control": {"type": "ephemeral"},
                }
            )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
        )
        return response.content[0].text

    def generate_stream(
        self,
        system_prompt: str,
        context_block: str,
        messages: list[dict],
    ) -> Iterator[str]:
        """Stream text deltas from Claude. Yields raw text chunks."""
        system = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if context_block:
            system.append(
                {
                    "type": "text",
                    "text": context_block,
                    "cache_control": {"type": "ephemeral"},
                }
            )

        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    # ------------------------------------------------------------------
    # Cheap/fast calls used by reranking, query rewrite, and image vision.
    # ------------------------------------------------------------------

    def quick_text(
        self,
        model: str,
        system_prompt: str,
        user_content: str | list[dict],
        max_tokens: int = 512,
    ) -> str:
        """One-shot call with no caching, returns raw text."""
        messages = [
            {
                "role": "user",
                "content": user_content
                if isinstance(user_content, list)
                else [{"type": "text", "text": user_content}],
            }
        ]
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
