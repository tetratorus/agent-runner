# claude-to-openai

A lightweight HTTP proxy that translates the Anthropic Messages API to the OpenAI Chat Completions API. Lets you point Claude Code (or any Anthropic SDK client) at a cheap OpenAI-compatible backend — DeepSeek by default, but it also works with OpenAI, Azure, Together AI, etc.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your DeepSeek API key (default backend)
export DEEPSEEK_API_KEY="sk-..."

# 3. Start the proxy
python proxy.py

# 4. Point Claude Code at it
export ANTHROPIC_BASE_URL=http://localhost:7777
claude
```

## How It Works

The proxy exposes the Anthropic `/v1/messages` endpoint and translates requests/responses to/from OpenAI format:

| Anthropic | ↔ | OpenAI |
|---|---|---|
| `POST /v1/messages` | → | `POST /v1/chat/completions` |
| `system` (top-level) | → | `messages[0].role = "system"` |
| `messages` (user/assistant only) | → | `messages` (system/user/assistant/tool) |
| `tools[].input_schema` | → | `tools[].function.parameters` |
| `tool_use` content blocks | → | `tool_calls` array |
| `tool_result` content blocks | → | `tool` role messages |
| `content` array (text + tool_use) | → | `message.content` + `message.tool_calls` |
| `stop_reason: "end_turn"` | ← | `finish_reason: "stop"` |
| `stop_reason: "tool_use"` | ← | `finish_reason: "tool_calls"` |
| `stop_reason: "max_tokens"` | ← | `finish_reason: "length"` |

Streaming (SSE) is fully supported with real-time translation of text and tool call deltas.

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` | *(required)* | API key for the upstream backend |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | OpenAI-compatible base URL |
| `OPENAI_MODEL` | `deepseek-chat` | Default model when mapping from Claude names |
| `PORT` | `7777` | Proxy listen port |

## Model Mapping

Claude model names are automatically mapped to the configured OpenAI model:

| Claude Name | Maps To |
|---|---|
| `claude-sonnet-4-6` | `OPENAI_MODEL` (default: `deepseek-chat`) |
| `claude-opus-4-6` | `OPENAI_MODEL` |
| `claude-3-5-sonnet` | `OPENAI_MODEL` |
| `gpt-4o-mini` | `gpt-4o-mini` (pass-through) |
| `deepseek-chat` | `deepseek-chat` (pass-through) |

You can also pass an OpenAI model name directly in the Anthropic request — any model name that doesn't start with `claude` is passed through unchanged.

## Example: OpenAI Backend

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.openai.com"
export OPENAI_MODEL="gpt-4o-mini"
python proxy.py

# In another terminal:
export ANTHROPIC_BASE_URL=http://localhost:7777
claude
```

Note: OpenAI's `gpt-5.x` and reasoning models (`o1`, `o3`, ...) reject `max_tokens` in favor of `max_completion_tokens`. The proxy doesn't currently translate that — stick with `gpt-4o`/`gpt-4o-mini` if you point it at real OpenAI, or use a backend that still accepts `max_tokens` (DeepSeek, Together, Azure, etc.).

## Running Tests

```bash
# Unit tests (no API key needed)
python -m pytest test_proxy.py -v

# Integration test (requires OPENAI_API_KEY)
python test_integration.py
```

## Architecture

- **proxy.py** — ASGI app (Starlette) with two endpoints:
  - `POST /v1/messages` — main translation endpoint
  - `GET /v1/models` — static model list
- **translator** — request/response/streaming format conversion
- **httpx** — async HTTP client to upstream OpenAI API
- **uvicorn** — ASGI server

## Limitations

- Anthropic → OpenAI only (not bidirectional)
- No load balancing or virtual keys (use LiteLLM Proxy for that)
- No caching or cost tracking
- Tool call `input` is serialized to JSON string for OpenAI, then parsed back — floating point edge cases may differ

## License

MIT
