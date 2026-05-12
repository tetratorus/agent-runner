#!/usr/bin/env python3
"""Unit tests for the claude-to-openai translation proxy."""

import json
import pytest
from proxy import (
    map_model,
    anthropic_to_openai_request,
    openai_to_anthropic_response,
    STOP_REASON_MAP,
)


class TestMapModel:
    def test_known_claude_model(self):
        assert map_model("claude-sonnet-4-6") == "deepseek-chat"

    def test_unknown_claude_model_defaults(self):
        assert map_model("claude-unknown-99") == "deepseek-chat"

    def test_openai_model_passes_through(self):
        assert map_model("gpt-4o-mini") == "gpt-4o-mini"
        assert map_model("deepseek-chat") == "deepseek-chat"


class TestRequestTranslation:
    def test_simple_text(self):
        body = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "Hello"}],
        }
        result = anthropic_to_openai_request(body)
        assert result["model"] == "deepseek-chat"
        assert result["messages"] == [{"role": "user", "content": "Hello"}]
        assert result["max_tokens"] == 1024

    def test_system_prompt_string(self):
        body = {
            "model": "claude-sonnet-4-6",
            "system": "You are helpful.",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        result = anthropic_to_openai_request(body)
        assert result["messages"][0] == {"role": "system", "content": "You are helpful."}
        assert result["messages"][1] == {"role": "user", "content": "Hello"}

    def test_system_prompt_blocks(self):
        body = {
            "model": "claude-sonnet-4-6",
            "system": [{"type": "text", "text": "Be nice."}],
            "messages": [{"role": "user", "content": "Hello"}],
        }
        result = anthropic_to_openai_request(body)
        assert result["messages"][0] == {"role": "system", "content": "Be nice."}

    def test_tools_translation(self):
        body = {
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "What's the weather?"}],
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "input_schema": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                    },
                }
            ],
        }
        result = anthropic_to_openai_request(body)
        assert result["tools"][0]["type"] == "function"
        assert result["tools"][0]["function"]["name"] == "get_weather"
        assert result["tools"][0]["function"]["parameters"]["type"] == "object"

    def test_tool_choice_auto(self):
        body = {
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Hi"}],
            "tool_choice": {"type": "auto"},
        }
        result = anthropic_to_openai_request(body)
        assert result["tool_choice"] == "auto"

    def test_tool_choice_any(self):
        body = {
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Hi"}],
            "tool_choice": {"type": "any"},
        }
        result = anthropic_to_openai_request(body)
        assert result["tool_choice"] == "required"

    def test_tool_choice_named(self):
        body = {
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Hi"}],
            "tool_choice": {"type": "tool", "name": "get_weather"},
        }
        result = anthropic_to_openai_request(body)
        assert result["tool_choice"]["type"] == "function"
        assert result["tool_choice"]["function"]["name"] == "get_weather"

    def test_assistant_with_tool_use(self):
        body = {
            "model": "claude-sonnet-4-6",
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Let me check"},
                        {"type": "tool_use", "id": "toolu_01", "name": "get_weather", "input": {"city": "SF"}},
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": "toolu_01", "content": "Sunny"},
                    ],
                },
            ],
        }
        result = anthropic_to_openai_request(body)
        assert result["messages"][0]["role"] == "assistant"
        assert result["messages"][0]["content"] == "Let me check"
        assert result["messages"][0]["tool_calls"][0]["function"]["name"] == "get_weather"
        assert result["messages"][0]["tool_calls"][0]["function"]["arguments"] == '{"city": "SF"}'
        assert result["messages"][1]["role"] == "tool"
        assert result["messages"][1]["tool_call_id"] == "toolu_01"
        assert result["messages"][1]["content"] == "Sunny"

    def test_tool_result_content_as_list(self):
        """Anthropic allows tool_result.content as a list of content blocks.
        Previously the proxy str()-ed the list, emitting Python repr."""
        body = {
            "model": "claude-sonnet-4-6",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_01",
                            "content": [
                                {"type": "text", "text": "Sunny, "},
                                {"type": "text", "text": "72F"},
                            ],
                        }
                    ],
                }
            ],
        }
        result = anthropic_to_openai_request(body)
        assert result["messages"][0]["role"] == "tool"
        assert result["messages"][0]["content"] == "Sunny, 72F"

    def test_user_message_text_and_tool_result_mixed(self):
        """When a user message has both tool_result and text blocks, both
        must be forwarded — tool_result as a tool message, text as a user
        message after it (OpenAI requires tool messages right after the
        assistant's tool_calls)."""
        body = {
            "model": "claude-sonnet-4-6",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": "toolu_01", "content": "Sunny"},
                        {"type": "text", "text": "Also tell me about the wind."},
                    ],
                }
            ],
        }
        result = anthropic_to_openai_request(body)
        assert len(result["messages"]) == 2
        assert result["messages"][0]["role"] == "tool"
        assert result["messages"][0]["tool_call_id"] == "toolu_01"
        assert result["messages"][0]["content"] == "Sunny"
        assert result["messages"][1]["role"] == "user"
        assert result["messages"][1]["content"] == "Also tell me about the wind."

    def test_streaming(self):
        body = {
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        result = anthropic_to_openai_request(body)
        assert result["stream"] is True
        assert result["stream_options"] == {"include_usage": True}


class TestResponseTranslation:
    def test_simple_text(self):
        openai_resp = {
            "id": "chatcmpl-123",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        result = openai_to_anthropic_response(openai_resp, "claude-sonnet-4-6")
        assert result["type"] == "message"
        assert result["role"] == "assistant"
        assert result["content"] == [{"type": "text", "text": "Hello!"}]
        assert result["stop_reason"] == "end_turn"
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 5

    def test_tool_calls(self):
        openai_resp = {
            "id": "chatcmpl-456",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"city": "SF"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }
        result = openai_to_anthropic_response(openai_resp, "claude-sonnet-4-6")
        assert result["stop_reason"] == "tool_use"
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "tool_use"
        assert result["content"][0]["id"] == "call_abc"
        assert result["content"][0]["name"] == "get_weather"
        assert result["content"][0]["input"]["city"] == "SF"

    def test_length_stop(self):
        openai_resp = {
            "id": "chatcmpl-789",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Truncated"},
                    "finish_reason": "length",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        result = openai_to_anthropic_response(openai_resp, "claude-sonnet-4-6")
        assert result["stop_reason"] == "max_tokens"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
