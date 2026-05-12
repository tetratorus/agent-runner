#!/usr/bin/env python3
"""
claude-to-openai: A translation proxy that exposes the Anthropic Messages API
and forwards to any OpenAI-compatible Chat Completions backend.

Defaults target DeepSeek so you can drive Claude Code through a cheap LLM
without changing the client. Override the env vars to point at OpenAI,
Together, Azure, etc.

Usage:
    export DEEPSEEK_API_KEY="sk-..."
    python proxy.py

Then point Claude Code at it:
    export ANTHROPIC_BASE_URL=http://localhost:7777
    claude
"""

import os
import sys
import json
import time
import uuid
import threading
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Single upstream API key. Reads DEEPSEEK_API_KEY because that's the default
# backend; if you override UPSTREAM_BASE_URL to point at OpenAI/Together/etc.,
# put that provider's key in DEEPSEEK_API_KEY too (or rename if you prefer).
UPSTREAM_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
UPSTREAM_BASE_URL = os.environ.get("UPSTREAM_BASE_URL", "https://api.deepseek.com")
UPSTREAM_MODEL = os.environ.get("UPSTREAM_MODEL", "deepseek-chat")
# Cap max_tokens before forwarding upstream. Claude clients often request
# 64000+ which exceeds smaller OpenAI models (e.g., gpt-4o-mini = 16384).
UPSTREAM_MAX_TOKENS = int(os.environ.get("UPSTREAM_MAX_TOKENS", "16384"))
PORT = int(os.environ.get("PORT", "7777"))

# Logging — one JSON object per line, appended at request completion.
LOG_FILE = os.environ.get("LOG_FILE", "proxy.log.jsonl")
_log_lock = threading.Lock()
_SENSITIVE_HEADERS = {"authorization", "x-api-key", "api-key", "anthropic-api-key", "openai-api-key"}


def _sanitize_headers(headers: dict) -> dict:
    return {k: ("[REDACTED]" if k.lower() in _SENSITIVE_HEADERS else v) for k, v in headers.items()}


def write_log(entry: dict) -> None:
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    try:
        line = json.dumps(entry, default=str)
    except (TypeError, ValueError) as e:
        line = json.dumps({"timestamp": entry["timestamp"], "log_error": str(e), "request_id": entry.get("request_id")})
    with _log_lock:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")

# Default model mapping: Anthropic names -> OpenAI names.
# Users can also pass an OpenAI model name directly (non-claude prefix).
DEFAULT_MODEL_MAP = {
    "claude-sonnet-4-6": UPSTREAM_MODEL,
    "claude-opus-4-6": UPSTREAM_MODEL,
    "claude-3-5-sonnet-20241022": UPSTREAM_MODEL,
    "claude-3-5-sonnet": UPSTREAM_MODEL,
    "claude-3-opus-20240229": UPSTREAM_MODEL,
    "claude-3-opus": UPSTREAM_MODEL,
    "claude-3-sonnet-20240229": UPSTREAM_MODEL,
    "claude-3-haiku-20240307": UPSTREAM_MODEL,
    "claude-2-1": UPSTREAM_MODEL,
    "claude-2": UPSTREAM_MODEL,
    "claude-instant-1-2": UPSTREAM_MODEL,
    "claude-instant-1": UPSTREAM_MODEL,
}


def map_model(anthropic_model: str) -> str:
    """Map an Anthropic model name to an OpenAI model name."""
    if anthropic_model in DEFAULT_MODEL_MAP:
        return DEFAULT_MODEL_MAP[anthropic_model]
    if not anthropic_model.startswith("claude"):
        return anthropic_model  # Assume it's already an OpenAI model name
    return UPSTREAM_MODEL


# Models we recognize as belonging to a hosted provider (OpenAI/Anthropic).
# When they hit /openai we remap them to the configured upstream model;
# anything else (deepseek-chat, deepseek-reasoner, qwen-*, ...) passes
# through, since it's presumably already a valid upstream model name.
_HOSTED_MODEL_PREFIXES = ("gpt-", "claude-", "o1", "o3", "o4")


def map_model_openai(model: str) -> str:
    if not model:
        return UPSTREAM_MODEL
    if model.startswith(_HOSTED_MODEL_PREFIXES):
        return UPSTREAM_MODEL
    return model


def _flatten_tool_result_content(content: Any) -> str:
    """Anthropic tool_result.content may be a string or a list of content blocks.
    OpenAI's tool role expects a flat string, so we extract text blocks."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)


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
                # Emit tool_result blocks as `tool` role messages first — OpenAI
                # requires them to immediately follow the assistant's tool_calls.
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_result":
                        openai_body["messages"].append({
                            "role": "tool",
                            "tool_call_id": c.get("tool_use_id", ""),
                            "content": _flatten_tool_result_content(c.get("content", "")),
                        })
                # Any text blocks follow as a separate user message.
                text_parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                if any(text_parts):
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
        openai_body["max_tokens"] = min(body["max_tokens"], UPSTREAM_MAX_TOKENS)

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
    return JSONResponse({
        "status": "ok",
        "upstream": UPSTREAM_BASE_URL,
        "model": UPSTREAM_MODEL,
        "endpoints": {
            "anthropic": "/claude/v1/messages",
            "openai": "/openai/v1/chat/completions",
        },
    })


async def claude_messages(request: Request):
    """Anthropic /v1/messages → OpenAI Chat Completions translator."""
    if not UPSTREAM_API_KEY:
        return JSONResponse(
            {"type": "error", "error": {"type": "authentication_error", "message": "UPSTREAM_API_KEY not configured on proxy"}},
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

    request_id = uuid.uuid4().hex[:12]
    start_time = time.time()
    upstream_url = f"{UPSTREAM_BASE_URL}/v1/chat/completions"
    log_entry: dict[str, Any] = {
        "request_id": request_id,
        "endpoint": "/claude/v1/messages",
        "upstream_url": upstream_url,
        "client_headers": _sanitize_headers(dict(request.headers)),
        "client_request_body": body,
        "upstream_request_body": openai_body,
        "streamed": is_streaming,
    }

    client = httpx.AsyncClient(timeout=300.0)

    try:
        if is_streaming:
            # Stream path: tee the upstream SSE bytes into a buffer while the
            # translator consumes them, so the log captures exactly what
            # DeepSeek sent. Open the upstream as a stream so we can read it
            # chunk-by-chunk; the client.stream() context must stay open
            # through the translator's iteration.
            stream_ctx = client.stream(
                "POST",
                upstream_url,
                headers={
                    "Authorization": f"Bearer {UPSTREAM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=openai_body,
            )
            resp = await stream_ctx.__aenter__()

            if resp.status_code != 200:
                err_text = (await resp.aread()).decode("utf-8", errors="replace")
                await stream_ctx.__aexit__(None, None, None)
                try:
                    err_body = json.loads(err_text)
                except Exception:
                    err_body = {"error": {"message": err_text}}
                log_entry["upstream_response_status"] = resp.status_code
                log_entry["upstream_response_headers"] = dict(resp.headers)
                log_entry["upstream_response_body"] = err_text
                log_entry["elapsed_ms"] = int((time.time() - start_time) * 1000)
                write_log(log_entry)
                anthropic_err = openai_error_to_anthropic(resp.status_code, err_body)
                return JSONResponse(anthropic_err, status_code=resp.status_code)

            upstream_chunks: list[bytes] = []

            async def _capture_upstream():
                async for chunk in resp.aiter_bytes():
                    upstream_chunks.append(chunk)
                    yield chunk

            async def stream_generator():
                try:
                    async for chunk in translate_stream(_capture_upstream(), anthropic_model):
                        yield chunk
                finally:
                    log_entry["upstream_response_status"] = resp.status_code
                    log_entry["upstream_response_headers"] = dict(resp.headers)
                    log_entry["upstream_response_body"] = b"".join(upstream_chunks).decode("utf-8", errors="replace")
                    log_entry["elapsed_ms"] = int((time.time() - start_time) * 1000)
                    write_log(log_entry)
                    await stream_ctx.__aexit__(None, None, None)
                    await client.aclose()

            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )

        # Non-streaming path
        resp = await client.post(
            upstream_url,
            headers={
                "Authorization": f"Bearer {UPSTREAM_API_KEY}",
                "Content-Type": "application/json",
            },
            json=openai_body,
        )

        log_entry["upstream_response_status"] = resp.status_code
        log_entry["upstream_response_headers"] = dict(resp.headers)
        try:
            log_entry["upstream_response_body"] = resp.json()
        except Exception:
            log_entry["upstream_response_body"] = resp.text
        log_entry["elapsed_ms"] = int((time.time() - start_time) * 1000)
        write_log(log_entry)

        if resp.status_code != 200:
            try:
                err_body = resp.json()
            except Exception:
                err_body = {"error": {"message": resp.text}}
            anthropic_err = openai_error_to_anthropic(resp.status_code, err_body)
            return JSONResponse(anthropic_err, status_code=resp.status_code)

        openai_data = resp.json()
        anthropic_data = openai_to_anthropic_response(openai_data, anthropic_model)
        return JSONResponse(anthropic_data)

    except httpx.RequestError as e:
        log_entry["upstream_error"] = str(e)
        log_entry["elapsed_ms"] = int((time.time() - start_time) * 1000)
        write_log(log_entry)
        return JSONResponse(
            {"type": "error", "error": {"type": "api_error", "message": str(e)}},
            status_code=502,
        )
    finally:
        if not is_streaming:
            await client.aclose()


async def claude_models(request: Request):
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


async def openai_chat_completions(request: Request):
    """OpenAI-shape passthrough — forwards to UPSTREAM_BASE_URL with the
    upstream API key and (optionally) remaps the model to UPSTREAM_MODEL.
    Lets agents that natively speak OpenAI route through the same proxy."""
    if not UPSTREAM_API_KEY:
        return JSONResponse(
            {"error": {"type": "authentication_error", "message": "API key not configured on proxy"}},
            status_code=500,
        )
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            {"error": {"type": "invalid_request_error", "message": "Invalid JSON"}},
            status_code=400,
        )

    body["model"] = map_model_openai(body.get("model", ""))
    is_streaming = bool(body.get("stream", False))
    upstream_url = f"{UPSTREAM_BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {UPSTREAM_API_KEY}",
        "Content-Type": "application/json",
    }

    request_id = uuid.uuid4().hex[:12]
    start_time = time.time()
    log_entry: dict[str, Any] = {
        "request_id": request_id,
        "endpoint": "/openai/v1/chat/completions",
        "upstream_url": upstream_url,
        "client_headers": _sanitize_headers(dict(request.headers)),
        "client_request_body": body,
        "upstream_request_body": body,
        "streamed": is_streaming,
    }

    if is_streaming:
        client = httpx.AsyncClient(timeout=300.0)
        upstream_chunks: list[bytes] = []

        async def gen():
            try:
                async with client.stream("POST", upstream_url, json=body, headers=headers) as upstream:
                    log_entry["upstream_response_status"] = upstream.status_code
                    log_entry["upstream_response_headers"] = dict(upstream.headers)
                    async for chunk in upstream.aiter_bytes():
                        upstream_chunks.append(chunk)
                        yield chunk
            except httpx.RequestError as e:
                log_entry["upstream_error"] = str(e)
            finally:
                log_entry["upstream_response_body"] = b"".join(upstream_chunks).decode("utf-8", errors="replace")
                log_entry["elapsed_ms"] = int((time.time() - start_time) * 1000)
                write_log(log_entry)
                await client.aclose()

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            resp = await client.post(upstream_url, json=body, headers=headers)
        except httpx.RequestError as e:
            log_entry["upstream_error"] = str(e)
            log_entry["elapsed_ms"] = int((time.time() - start_time) * 1000)
            write_log(log_entry)
            return JSONResponse(
                {"error": {"type": "api_error", "message": str(e)}},
                status_code=502,
            )

        log_entry["upstream_response_status"] = resp.status_code
        log_entry["upstream_response_headers"] = dict(resp.headers)
        try:
            log_entry["upstream_response_body"] = resp.json()
        except Exception:
            log_entry["upstream_response_body"] = resp.text
        log_entry["elapsed_ms"] = int((time.time() - start_time) * 1000)
        write_log(log_entry)

        try:
            return JSONResponse(resp.json(), status_code=resp.status_code)
        except json.JSONDecodeError:
            return JSONResponse(
                {"error": {"type": "api_error", "message": resp.text}},
                status_code=resp.status_code or 502,
            )


async def openai_models(request: Request):
    return JSONResponse({
        "object": "list",
        "data": [{"id": UPSTREAM_MODEL, "object": "model", "owned_by": "proxy"}],
    })


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = Starlette(
    routes=[
        Route("/", healthcheck, methods=["GET"]),
        # Anthropic-shape clients (Claude Code, anthropic-sdk, ...).
        Route("/claude/v1/messages", claude_messages, methods=["POST"]),
        Route("/claude/v1/models", claude_models, methods=["GET"]),
        # OpenAI-shape clients (Codex, Aider, OpenCode, ...).
        Route("/openai/v1/chat/completions", openai_chat_completions, methods=["POST"]),
        Route("/openai/v1/models", openai_models, methods=["GET"]),
    ],
)


if __name__ == "__main__":
    import uvicorn
    if not UPSTREAM_API_KEY:
        print("ERROR: UPSTREAM_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)
    print(f"claude-to-openai proxy starting on port {PORT}")
    print(f"Forwarding to: {UPSTREAM_BASE_URL}")
    print(f"Default model: {UPSTREAM_MODEL}")
    print(f"Logging to:    {os.path.abspath(LOG_FILE)}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
