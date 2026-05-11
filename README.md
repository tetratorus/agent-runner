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

## Requirements

- macOS (Intel or Apple Silicon)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- API keys for the agents you want to use

## Available Agents

| Agent | Key | Needs |
|-------|-----|-------|
| Claude Code | `claude-code` | `ANTHROPIC_API_KEY` |
| Codex CLI | `codex` | `OPENAI_API_KEY` |
| Aider | `aider` | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` |

## Commands

```bash
./agent-run setup                          # Build all Docker images
./agent-run list                           # List agents + env status
./agent-run claude-code --prompt "..." --workspace ./project
./agent-run codex --prompt-file ./task.md --workspace ./project
./agent-run aider --prompt "..." --workspace ./project --timeout 300
./agent-run all --prompt "..." --workspace ./project --out ./results
./agent-run claude-code,codex --prompt "..." --workspace ./project
```

## How It Works

1. **Docker isolation** — each agent runs in its own container with only its required runtime (Node.js for Claude/Codex, Python for Aider)
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
│   └── Dockerfile.aider   # Aider
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
