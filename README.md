# agent-run

Run popular coding agents (Claude Code, Codex CLI, Aider) in isolated Docker containers on macOS. Pass a prompt, mount your project, run multiple agents concurrently, compare results.

## Quick Start

```bash
# 1. Clone / copy this directory
cd agent-runner

# 2. Set API keys
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."

# 3. Build images (one-time)
./agent-run setup

# 4. Run an agent
./agent-run claude-code \
  --prompt "Fix the auth bug in login.py" \
  --workspace ./my-project

# 5. Run multiple agents on the same task
./agent-run all \
  --prompt "Refactor utils.py to use async/await" \
  --workspace ./my-project \
  --out ./results
```

## Route every agent through DeepSeek (or any cheap OpenAI-compatible backend)

The [`proxy/`](./proxy) directory is a small translator that exposes two
endpoints — one Anthropic-shape, one OpenAI-shape — and forwards both to
DeepSeek by default. Point each agent at the matching prefix and they all
end up calling the same cheap backend.

```bash
# 1. Start the proxy on the host
cd proxy && pip install -r requirements.txt
DEEPSEEK_API_KEY=sk-... python3 proxy.py     # listens on :7777

# 2. Run any agent against it
ANTHROPIC_API_KEY=dummy \
ANTHROPIC_BASE_URL=http://host.docker.internal:7777/claude \
  ./agent-run claude-code --prompt "..." --workspace ./my-project

OPENAI_API_KEY=dummy \
OPENAI_BASE_URL=http://host.docker.internal:7777/openai/v1 \
  ./agent-run codex --prompt "..." --workspace ./my-project
```

Endpoints:
- `http://localhost:7777/claude` — Anthropic-shape (Claude Code).
- `http://localhost:7777/openai/v1` — OpenAI-shape (Codex, Goose, ...).

See [`proxy/README.md`](./proxy/README.md) for full details.

### Agent status through the DeepSeek proxy

| Agent | Status | Notes |
|---|---|---|
| `claude-code` | ✅ works | `ANTHROPIC_BASE_URL=…/claude` |
| `codex` | ✅ works | Pinned to `@openai/codex@0.50.0` — newer versions force the OpenAI-only Responses API |
| `goose` | ✅ works | `OPENAI_HOST=…/openai` + `GOOSE_PROVIDER=openai GOOSE_MODEL=deepseek-chat` |
| `opencode` | ❌ blocked | Uses the Responses API for OpenAI models; needs a Responses translator in the proxy |
| `pi` | ❌ blocked | Needs `~/.pi/agent/models.json` with a custom provider entry |

## Requirements

- macOS (Intel or Apple Silicon)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- API keys for the agents you want to use

## Available Agents

| Agent | Key | Needs | Notes |
|-------|-----|-------|-------|
| Claude Code | `claude-code` | `ANTHROPIC_API_KEY` | Anthropic official. S-tier reasoning. |
| Codex CLI | `codex` | `OPENAI_API_KEY` | OpenAI official. Token-efficient. Pinned to 0.50.0 for Chat Completions support. |
| Goose | `goose` | `ANTHROPIC_API_KEY` | Block's open-source agent. Model-agnostic, MCP. |
| OpenCode | `opencode` | `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | Multi-provider fork. |
| Pi | `pi` | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` | Composable agent. Skills, AGENTS.md. |

## Commands

```bash
./agent-run setup                          # Build all Docker images
./agent-run list                           # List agents + env status
./agent-run claude-code --prompt "..." --workspace ./project
./agent-run codex --prompt-file ./task.md --workspace ./project
./agent-run goose --prompt "..." --workspace ./project --timeout 300
./agent-run all --prompt "..." --workspace ./project --out ./results
./agent-run claude-code,codex --prompt "..." --workspace ./project
```

## How It Works

1. **Docker isolation** — each agent runs in its own container with only its required runtime
2. **Volume mount** — your project directory is mounted read-write at `/workspace`
3. **API keys** — passed as environment variables, never written to disk inside the container
4. **Results** — output logs and modified files are written to `./results/<agent>/<timestamp>/`
5. **Concurrent** — run multiple agents simultaneously; each gets its own container

## Project Structure

```
agent-runner/
├── agent-run              # Main CLI
├── docker/
│   ├── Dockerfile.base    # Debian + Node + Python
│   ├── Dockerfile.claude  # Claude Code
│   ├── Dockerfile.codex   # Codex CLI
│   └── Dockerfile.<agent> # one per agent listed above
├── results/               # Created on first run
└── README.md
```

## Adding New Agents

1. Create `docker/Dockerfile.<name>`
2. Add entry to `AGENTS` dict in `agent-run`
3. Run `./agent-run setup`

## Notes

- Containers run as your macOS user ID (not root), so file permissions match the host
- `--platform linux/amd64` is used for compatibility; Rosetta 2 handles translation on Apple Silicon
- Each container is ephemeral (`--rm`); only the results directory persists
- Default timeout is 10 minutes; use `--timeout` to adjust
