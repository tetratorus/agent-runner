#!/usr/bin/env python3
"""Integration tests for claude-to-openai proxy hitting the real OpenAI API.

Requires DEEPSEEK_API_KEY in the environment. Override the model with
UPSTREAM_TEST_MODEL (default: gpt-4o-mini).
"""

import json
import os

import pytest
from starlette.testclient import TestClient

import proxy as proxy_module

if not os.environ.get("DEEPSEEK_API_KEY"):
    pytest.skip("DEEPSEEK_API_KEY not set", allow_module_level=True)

MODEL = os.environ.get("UPSTREAM_TEST_MODEL", "deepseek-chat")


@pytest.fixture
def client():
    """TestClient with the proxy reconfigured to use the real test model."""
    original_model = proxy_module.UPSTREAM_MODEL
    original_map = dict(proxy_module.DEFAULT_MODEL_MAP)
    proxy_module.UPSTREAM_MODEL = MODEL
    for k in list(proxy_module.DEFAULT_MODEL_MAP):
        proxy_module.DEFAULT_MODEL_MAP[k] = MODEL
    yield TestClient(proxy_module.app)
    proxy_module.UPSTREAM_MODEL = original_model
    proxy_module.DEFAULT_MODEL_MAP.clear()
    proxy_module.DEFAULT_MODEL_MAP.update(original_map)


def test_healthcheck(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_non_streaming_text(client):
    resp = client.post(
        "/claude/v1/messages",
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 50,
            "messages": [
                {"role": "user", "content": "Reply with exactly one word: pong"}
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["type"] == "message"
    assert data["role"] == "assistant"
    assert data["stop_reason"] in ("end_turn", "max_tokens")
    text = "".join(
        b.get("text", "") for b in data["content"] if b.get("type") == "text"
    )
    assert text.strip(), f"expected non-empty text, got: {text!r}"
    assert data["usage"]["input_tokens"] > 0
    assert data["usage"]["output_tokens"] > 0


def test_non_streaming_tool_call(client):
    resp = client.post(
        "/claude/v1/messages",
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 200,
            "messages": [
                {
                    "role": "user",
                    "content": "What's the weather in San Francisco? Use the tool.",
                }
            ],
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get the current weather for a city",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "City name, e.g. San Francisco",
                            }
                        },
                        "required": ["city"],
                    },
                }
            ],
            "tool_choice": {"type": "any"},
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["stop_reason"] == "tool_use"
    tool_uses = [b for b in data["content"] if b.get("type") == "tool_use"]
    assert tool_uses, f"no tool_use blocks: {data}"
    tu = tool_uses[0]
    assert tu["name"] == "get_weather"
    assert "city" in tu["input"]
    assert "san francisco" in tu["input"]["city"].lower()


def test_system_prompt(client):
    resp = client.post(
        "/claude/v1/messages",
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 20,
            "system": "You always respond with exactly one word: PIRATE",
            "messages": [{"role": "user", "content": "Hello there."}],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    text = "".join(
        b.get("text", "") for b in data["content"] if b.get("type") == "text"
    )
    assert "pirate" in text.lower(), f"expected 'pirate', got: {text!r}"


def test_streaming_text(client):
    text_parts: list[str] = []
    event_types: list[str] = []
    final_usage: dict | None = None

    with client.stream(
        "POST",
        "/claude/v1/messages",
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 30,
            "stream": True,
            "messages": [
                {"role": "user", "content": "Reply with exactly one word: stream"}
            ],
        },
    ) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("event: "):
                event_types.append(line[7:].strip())
            elif line.startswith("data: "):
                try:
                    payload = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if payload.get("type") == "content_block_delta":
                    delta = payload.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text_parts.append(delta.get("text", ""))
                elif payload.get("type") == "message_delta":
                    if isinstance(payload.get("usage"), dict):
                        final_usage = payload["usage"]

    assert "message_start" in event_types
    assert "message_delta" in event_types
    assert "message_stop" in event_types
    full_text = "".join(text_parts)
    assert full_text.strip(), f"expected non-empty streamed text, got: {full_text!r}"
    assert final_usage is not None, "message_delta did not include usage"
    assert final_usage.get("input_tokens", 0) > 0, f"input_tokens={final_usage}"
    assert final_usage.get("output_tokens", 0) > 0, f"output_tokens={final_usage}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
