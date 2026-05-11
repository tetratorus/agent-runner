#!/usr/bin/env python3
"""
claude-to-openai: A translation proxy that exposes the Anthropic Messages API
and forwards requests to the OpenAI Chat Completions API.

Usage:
    export OPENAI_API_KEY="sk-..."
    export OPENAI_MODEL="gpt-5.4"
    python proxy.py

Then point Claude Code at it:
    export ANTHROPIC_BASE_URL=http://localhost:7777
    claude
"""

import os
import sys
import json
import uuid
from typing import Any, AsyncGenerator

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4")
# Cap max_tokens before forwarding upstream. Claude clients often request
# 64000+ which exceeds smaller OpenAI models (e.g., gpt-4o-mini = 16384).
OPENAI_MAX_TOKENS = int(os.environ.get("OPENAI_MAX_TOKENS", "16384"))
PORT = int(os.environ.get("PORT", "7777"))

# Default model mapping: Anthropic names -> OpenAI names.
# Users can also pass an OpenAI model name directly (non-claude prefix).
DEFAULT_MODEL_MAP = {
    "claude-sonnet-4-6": OPENAI_MODEL,
    "claude-opus-4-6": OPENAI_MODEL,
    "claude-3-5-sonnet-20241022": OPENAI_MODEL,
    "claude-3-5-sonnet": OPENAI_MODEL,
    "claude-3-opus-20240229": OPENAI_MODEL,
    "claude-3-opus": OPENAI_MODEL,
    "claude-3-sonnet-20240229": OPENAI_MODEL,
    "claude-3-haiku-20240307": OPENAI_MODEL,
    "claude-2-1": OPENAI_MODEL,
    "claude-2": OPENAI_MODEL,
    "claude-instant-1-2": OPENAI_MODEL,
    "claude-instant-1": OPENAI_MODEL,
}


def map_model(anthropic_model: str) -> str:
    """Map an Anthropic model name to an OpenAI model name."""
    if anthropic_model in DEFAULT_MODEL_MAP:
        return DEFAULT_MODEL_MAP[anthropic_model]
    if not anthropic_model.startswith("claude"):
        return anthropic_model  # Assume it's already an OpenAI model name
    return OPENAI_MODEL


# ---------------------------------------------------------------------------
# Request translation: Anthropic -> OpenAI
# ---------------------------------------------------------------------------

def anthropic_to_openai_request(body: dict) -> dict:
    """Translate an Anthropic Messages API request to OpenAI Chat Completions format."""
    openai_body: dict[str, Any] = {
        "model": map_model(body.get("model", "")),
        "messages": [],
    }

    # System prompt ---------------------------------------------------------
    system = body.get("system")
    if system is not None:
        if isinstance(system, str):
            openai_body["messages"].append({"role": "system", "content": system})
        elif isinstance(system, list):
            texts = [s.get("text", "") for s in system if isinstance(s, dict)]
            openai_body["messages"].append({"role": "system", "content": "".join(texts)})

    # Messages --------------------------------------------------------------
    for msg in body.get("messages", []):
        role = msg.get("role")
        content = msg.get("content")

        if role == "user":
            if isinstance(content, str):
                openai_body["messages"].append({"role": "user", "content": content})
            elif isinstance(content, list):
                # Check for tool_result blocks vs regular text blocks
                tool_results = [c for c in content if isinstance(c, dict) and c.get("type") == "tool_result"]
                if tool_results:
                    for tr in tool_results:
                        openai_body["messages"].append({
                            "role": "tool",
                            "tool_call_id": tr.get("tool_use_id", ""),
                            "content": str(tr.get("content", "")),
                        })
                else:
                    text_parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                    openai_body["messages"].append({"role": "user", "content": "".join(text_parts)})

        elif role == "assistant":
            if isinstance(content, str):
                openai_body["messages"].append({"role": "assistant", "content": content})
            elif isinstance(content, list):
                text_parts = []
                tool_calls = []
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "text":
                        text_parts.append(c.get("text", ""))
                    elif c.get("type") == "tool_use":
                        tool_calls.append({
                            "id": c.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": c.get("name", ""),
                                "arguments": json.dumps(c.get("input", {})),
                            },
                        })

                assistant_msg: dict[str, Any] = {"role": "assistant"}
                if text_parts:
                    assistant_msg["content"] = "".join(text_parts)
                else:
                    assistant_msg["content"] = None
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                openai_body["messages"].append(assistant_msg)

    # Tools -----------------------------------------------------------------
    if "tools" in body:
        openai_tools = []
        for tool in body["tools"]:
            if not isinstance(tool, dict):
                continue
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            })
        if openai_tools:
            openai_body["tools"] = openai_tools

    # Tool choice -----------------------------------------------------------
    tool_choice = body.get("tool_choice")
    if tool_choice is not None:
        if isinstance(tool_choice, dict):
            tc_type = tool_choice.get("type")
            if tc_type == "auto":
                openai_body["tool_choice"] = "auto"
            elif tc_type == "any":
                openai_body["tool_choice"] = "required"
            elif tc_type == "tool":
                openai_body["tool_choice"] = {
                    "type": "function",
                    "function": {"name": tool_choice.get("name", "")},
                }
        else:
            openai_body["tool_choice"] = tool_choice

    # Max tokens ------------------------------------------------------------
    if "max_tokens" in body:
        openai_body["max_tokens"] = min(body["max_tokens"], OPENAI_MAX_TOKENS)

    # Temperature, top_p, stop ----------------------------------------------
    if "temperature" in body:
        openai_body["temperature"] = body["temperature"]
    if "top_p" in body:
        openai_body["top_p"] = body["top_p"]
    if "stop_sequences" in body:
        openai_body["stop"] = body["stop_sequences"]

    # Streaming -------------------------------------------------------------
    if body.get("stream", False):
        openai_body["stream"] = True
        openai_body["stream_options"] = {"include_usage": True}

    # Anthropic 'metadata' is dropped — OpenAI rejects it unless store=true.

    return openai_body


# ---------------------------------------------------------------------------
# Response translation: OpenAI -> Anthropic
# ---------------------------------------------------------------------------

STOP_REASON_MAP = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "end_turn",
}


def openai_to_anthropic_response(openai_resp: dict, anthropic_model: str) -> dict:
    """Translate an OpenAI Chat Completions response to Anthropic Messages format."""
    choice = openai_resp.get("choices", [{}])[0]
    message = choice.get("message", {})

    content: list[dict] = []
    text = message.get("content")
    if text:
        content.append({"type": "text", "text": text})

    for tc in message.get("tool_calls", []):
        func = tc.get("function", {})
        args_str = func.get("arguments", "{}")
        try:
            args = json.loads(args_str) if args_str else {}
        except json.JSONDecodeError:
            args = {}
        content.append({
            "type": "tool_use",
            "id": tc.get("id", ""),
            "name": func.get("name", ""),
            "input": args,
        })

    stop_reason = choice.get("finish_reason", "stop")
    usage = openai_resp.get("usage", {})

    return {
        "id": f"msg_{openai_resp.get('id', uuid.uuid4().hex).replace('chatcmpl-', '')}",
        "type": "message",
        "role": "assistant",
        "model": anthropic_model,
        "content": content,
        "stop_reason": STOP_REASON_MAP.get(stop_reason, "end_turn"),
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


# ---------------------------------------------------------------------------
# Streaming translation: OpenAI SSE -> Anthropic SSE
# ---------------------------------------------------------------------------

async def translate_stream(
    openai_stream: AsyncGenerator[bytes, None],
    anthropic_model: str,
) -> AsyncGenerator[str, None]:
    """Translate an OpenAI SSE stream into Anthropic SSE events."""
    message_id = None
    text_buffer = ""
    tool_calls: dict[int, dict[str, Any]] = {}
    finish_reason = None
    has_text_block = False
    usage = {"input_tokens": 0, "output_tokens": 0}

    # message_start
    msg_start = json.dumps({
        "type": "message_start",
        "message": {
            "id": "",
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": anthropic_model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 1},
        },
    })
    yield f"event: message_start\ndata: {msg_start}\n\n"

    async for chunk in openai_stream:
        lines = chunk.decode("utf-8", errors="replace").split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith(":"):
                continue
            if line == "data: [DONE]":
                break

            if not line.startswith("data: "):
                continue

            try:
                data = json.loads(line[6:])
            except json.JSONDecodeError:
                continue

            choices = data.get("choices") or []
            choice = choices[0] if choices else {}
            delta = choice.get("delta", {}) if isinstance(choice, dict) else {}

            if message_id is None and data.get("id"):
                message_id = data["id"]

            # Text streaming
            content_delta = delta.get("content")
            if content_delta:
                if not has_text_block:
                    has_text_block = True
                    cbs = json.dumps({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})
                    yield f"event: content_block_start\ndata: {cbs}\n\n"
                cbd = json.dumps({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": content_delta}})
                yield f"event: content_block_delta\ndata: {cbd}\n\n"

            # Tool call streaming
            tc_deltas = delta.get("tool_calls", [])
            if tc_deltas:
                for tc_delta in tc_deltas:
                    if not isinstance(tc_delta, dict):
                        continue
                    idx = tc_delta.get("index", 0)
                    if idx not in tool_calls:
                        tool_calls[idx] = {"id": "", "name": "", "arguments": ""}

                    if "id" in tc_delta:
                        tool_calls[idx]["id"] = tc_delta["id"]
                    if "type" in tc_delta:
                        pass  # Always "function"
                    func_delta = tc_delta.get("function", {})
                    if isinstance(func_delta, dict):
                        if "name" in func_delta:
                            tool_calls[idx]["name"] = func_delta["name"]
                        if "arguments" in func_delta:
                            tool_calls[idx]["arguments"] += func_delta["arguments"]

            # Finish reason
            fr = choice.get("finish_reason") if isinstance(choice, dict) else None
            if fr:
                finish_reason = fr

            # Usage (only present in the final chunk when stream_options.include_usage=true)
            chunk_usage = data.get("usage")
            if isinstance(chunk_usage, dict):
                usage["input_tokens"] = chunk_usage.get("prompt_tokens", usage["input_tokens"])
                usage["output_tokens"] = chunk_usage.get("completion_tokens", usage["output_tokens"])

    # text content_block_stop
    if has_text_block:
        cbs_stop = json.dumps({"type": "content_block_stop", "index": 0})
        yield f"event: content_block_stop\ndata: {cbs_stop}\n\n"

    # Tool use blocks
    base_idx = 1 if has_text_block else 0
    for idx, tc in sorted(tool_calls.items()):
        if not tc.get("id"):
            continue

        tcs = json.dumps({"type": "content_block_start", "index": base_idx + idx, "content_block": {"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": {}}})
        yield f"event: content_block_start\ndata: {tcs}\n\n"

        args = tc.get("arguments", "")
        if args:
            tcd = json.dumps({"type": "content_block_delta", "index": base_idx + idx, "delta": {"type": "input_json_delta", "partial_json": args}})
            yield f"event: content_block_delta\ndata: {tcd}\n\n"

        tc_stop = json.dumps({"type": "content_block_stop", "index": base_idx + idx})
        yield f"event: content_block_stop\ndata: {tc_stop}\n\n"

    # message_delta — Anthropic puts final cumulative usage here
    anthropic_stop = STOP_REASON_MAP.get(finish_reason, "end_turn") if finish_reason else None
    msg_delta: dict[str, Any] = {"type": "message_delta", "delta": {}, "usage": usage}
    if anthropic_stop:
        msg_delta["delta"]["stop_reason"] = anthropic_stop

    msg_delta_json = json.dumps(msg_delta)
    yield f"event: message_delta\ndata: {msg_delta_json}\n\n"

    # message_stop
    msg_stop = json.dumps({"type": "message_stop"})
    yield f"event: message_stop\ndata: {msg_stop}\n\n"


# ---------------------------------------------------------------------------
# Error translation
# ---------------------------------------------------------------------------

def openai_error_to_anthropic(status_code: int, openai_error: dict) -> dict:
    """Translate an OpenAI error response to Anthropic error format."""
    error_info = openai_error.get("error", {})
    return {
        "type": "error",
        "error": {
            "type": "api_error" if status_code >= 500 else "invalid_request_error",
            "message": error_info.get("message", "Unknown error"),
        },
    }


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------

async def healthcheck(request: Request):
    return JSONResponse({"status": "ok", "proxy": "claude-to-openai"})


async def messages(request: Request):
    """Main Anthropic /v1/messages endpoint."""
    if not OPENAI_API_KEY:
        return JSONResponse(
            {"type": "error", "error": {"type": "authentication_error", "message": "OPENAI_API_KEY not configured on proxy"}},
            status_code=500,
        )
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            {"type": "error", "error": {"type": "invalid_request_error", "message": "Invalid JSON"}},
            status_code=400,
        )

    anthropic_model = body.get("model", "unknown")
    openai_body = anthropic_to_openai_request(body)
    is_streaming = openai_body.get("stream", False)

    client = httpx.AsyncClient(timeout=300.0)

    try:
        resp = await client.post(
            f"{OPENAI_BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=openai_body,
        )

        if resp.status_code != 200:
            try:
                err_body = resp.json()
            except Exception:
                err_body = {"error": {"message": resp.text}}
            anthropic_err = openai_error_to_anthropic(resp.status_code, err_body)
            return JSONResponse(anthropic_err, status_code=resp.status_code)

        if is_streaming:
            async def stream_generator():
                async for chunk in translate_stream(resp.aiter_bytes(), anthropic_model):
                    yield chunk

            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        else:
            openai_data = resp.json()
            anthropic_data = openai_to_anthropic_response(openai_data, anthropic_model)
            return JSONResponse(anthropic_data)

    except httpx.RequestError as e:
        return JSONResponse(
            {"type": "error", "error": {"type": "api_error", "message": str(e)}},
            status_code=502,
        )
    finally:
        await client.aclose()


async def models(request: Request):
    """Return a static list of models in Anthropic format."""
    return JSONResponse({
        "data": [
            {
                "id": "claude-sonnet-4-6",
                "object": "model",
                "created": 1700000000,
                "owned_by": "anthropic",
            },
        ],
        "object": "list",
    })


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = Starlette(
    routes=[
        Route("/", healthcheck, methods=["GET"]),
        Route("/v1/messages", messages, methods=["POST"]),
        Route("/v1/models", models, methods=["GET"]),
    ],
)


if __name__ == "__main__":
    import uvicorn
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)
    print(f"claude-to-openai proxy starting on port {PORT}")
    print(f"Forwarding to: {OPENAI_BASE_URL}")
    print(f"Default model: {OPENAI_MODEL}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
