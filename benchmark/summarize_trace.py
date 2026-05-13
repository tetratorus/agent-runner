#!/usr/bin/env python3
"""Render a clean turn-by-turn transcript from a proxy.jsonl cell slice.

Each proxy.jsonl entry's `client_request_body.messages` contains the *entire*
conversation up to that point — so the last entry has the full history except
the assistant's final reply (which lives in that entry's response). We:

  1. Take the messages array from the last proxy.jsonl entry.
  2. Append the assistant's final reply, parsed from the last entry's
     upstream_response_body.
  3. Render each turn as plain text with explicit TOOL_USE / TOOL_RESULT
     blocks so a judge can scan it without parsing wire-format JSON.

The output is ~20× smaller than raw proxy.jsonl and is what grade.py hands the
judge.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _text_of(block) -> str:
    """Pull readable text out of an Anthropic content block."""
    if isinstance(block, str):
        return block
    if not isinstance(block, dict):
        return ""
    t = block.get("type")
    if t == "text":
        return block.get("text", "")
    if t == "thinking":
        return f"[thinking] {block.get('thinking', '')}"
    return ""


def _render_message(msg: dict, idx: int) -> list[str]:
    role = msg.get("role", "?")
    content = msg.get("content")
    out = [f"=== turn {idx}: {role} ==="]
    if isinstance(content, str):
        out.append(content)
        return out
    if not isinstance(content, list):
        return out
    for block in content:
        if not isinstance(block, dict):
            continue
        t = block.get("type")
        if t in ("text", "thinking"):
            out.append(_text_of(block))
        elif t == "tool_use":
            name = block.get("name", "?")
            inp = block.get("input", {})
            try:
                args = json.dumps(inp, indent=2)
            except (TypeError, ValueError):
                args = str(inp)
            out.append(f"TOOL_USE: {name}\n{args}")
        elif t == "tool_result":
            tc = block.get("content")
            if isinstance(tc, str):
                body = tc
            elif isinstance(tc, list):
                body = "\n".join(_text_of(b) for b in tc if isinstance(b, dict))
            else:
                body = json.dumps(tc) if tc is not None else ""
            tool_id = block.get("tool_use_id", "")
            out.append(f"TOOL_RESULT (id={tool_id}):\n{body}")
    return out


def _parse_streamed_response(upstream_body) -> str:
    """Best-effort: pull the assistant's text out of a streamed Anthropic
    SSE body. Falls back to "" on anything unrecognized."""
    if not isinstance(upstream_body, str):
        return ""
    pieces = []
    for line in upstream_body.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        # OpenAI-style chunk
        choices = obj.get("choices") or []
        for choice in choices:
            delta = choice.get("delta") or {}
            piece = delta.get("content")
            if isinstance(piece, str):
                pieces.append(piece)
        # Anthropic content_block_delta chunks
        if obj.get("type") == "content_block_delta":
            d = obj.get("delta") or {}
            if d.get("type") == "text_delta":
                pieces.append(d.get("text", ""))
    return "".join(pieces).strip()


def summarize(proxy_jsonl: Path) -> str:
    entries = []
    for line in proxy_jsonl.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    if not entries:
        return "(empty proxy log — agent made no LLM calls)\n"

    last = entries[-1]
    body = last.get("client_request_body") or {}
    messages = body.get("messages") or []

    lines = [
        f"# Trace summary",
        f"# {len(entries)} LLM round-trips, model={body.get('model','?')}",
        "",
    ]
    for i, msg in enumerate(messages, 1):
        lines.extend(_render_message(msg, i))
        lines.append("")

    final_text = _parse_streamed_response(last.get("upstream_response_body"))
    if final_text:
        lines.append(f"=== turn {len(messages)+1}: assistant (final) ===")
        lines.append(final_text)
        lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: summarize_trace.py <proxy.jsonl> [out.txt]", file=sys.stderr)
        return 1
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"ERROR: {src} not found", file=sys.stderr)
        return 1
    text = summarize(src)
    if len(sys.argv) >= 3:
        Path(sys.argv[2]).write_text(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
