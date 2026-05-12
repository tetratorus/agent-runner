#!/usr/bin/env python3
"""Run the agentic-wallet benchmark.

For each (wallet, agent, test) cell:
  1. Build the prompt from template.txt + wallet's sdk.md + test prompt.
  2. Snapshot the proxy log size (so we can slice this cell's entries later).
  3. Snapshot the wallet's workspace (clone it to a fresh per-cell dir so the
     agent's edits don't bleed into the next cell).
  4. Run `agent-run <agent>` with the prompt + the per-cell workspace.
  5. Capture: agent stdout/exit code, the proxy log slice for the cell, and
     the post-run workspace (diff vs the wallet's template workspace).
  6. Hand the bundle to grade.py for pass/fail.

Outputs go to `results/<run-id>/<wallet>/<agent>/<test_id>/`:
  - prompt.txt
  - stdout.log
  - proxy.jsonl           (the slice for this cell)
  - workspace/            (post-run files)
  - grade.json            (pass/fail + reason from the judge)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from datetime import datetime


BENCH_DIR = Path(__file__).parent.resolve()
REPO_DIR = BENCH_DIR.parent
AGENT_RUN = REPO_DIR / "agent-run"
PROXY_LOG = Path(os.environ.get("LOG_FILE", REPO_DIR / "proxy.log.jsonl"))


# Agents in agent-run's AGENTS dict that are wired up against the proxy.
# Skip gemini (removed) and any agent that can't speak through the proxy.
DEFAULT_AGENTS = ["claude-code", "codex", "aider", "goose", "nanobot", "pi"]

# Which wallets each agent can drive. phantom-mcp needs MCP support.
MCP_CAPABLE_AGENTS = {"claude-code"}


def discover_tests() -> list[tuple[str, str, Path]]:
    """Return (test_id, category, path) for every test prompt."""
    out = []
    for cat_dir in sorted((BENCH_DIR / "tests").iterdir()):
        if not cat_dir.is_dir():
            continue
        for prompt_file in sorted(cat_dir.glob("*.txt")):
            out.append((prompt_file.stem, cat_dir.name, prompt_file))
    return out


def discover_wallets() -> list[str]:
    return sorted(d.name for d in (BENCH_DIR / "wallets").iterdir() if d.is_dir())


def build_prompt(template: str, wallet: str, task: str) -> str:
    return template.replace("{{WALLET_SDK}}", wallet).replace("{{TASK}}", task)


def proxy_log_size() -> int:
    try:
        return PROXY_LOG.stat().st_size
    except FileNotFoundError:
        return 0


def slice_proxy_log(start: int, end: int) -> list[dict]:
    if not PROXY_LOG.exists():
        return []
    with open(PROXY_LOG, "rb") as f:
        f.seek(start)
        raw = f.read(end - start)
    out = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def run_cell(
    wallet: str,
    agent: str,
    test_id: str,
    category: str,
    prompt_path: Path,
    template: str,
    out_root: Path,
    timeout: int,
) -> dict:
    """Run one (wallet, agent, test) cell. Returns a summary dict."""
    cell_dir = out_root / wallet / agent / test_id
    cell_dir.mkdir(parents=True, exist_ok=True)

    wallet_dir = BENCH_DIR / "wallets" / wallet
    task = prompt_path.read_text().strip()
    prompt = build_prompt(template, wallet, task)
    (cell_dir / "prompt.txt").write_text(prompt)

    # Per-cell workspace: clone the wallet's template workspace.
    template_ws = wallet_dir / "workspace"
    cell_ws = cell_dir / "workspace"
    if template_ws.exists():
        shutil.copytree(template_ws, cell_ws, dirs_exist_ok=True)
    else:
        cell_ws.mkdir(parents=True, exist_ok=True)

    # Snapshot proxy log position before the run.
    log_start = proxy_log_size()
    started_at = datetime.now().isoformat()
    t0 = time.time()

    cmd = [
        str(AGENT_RUN), agent,
        "--prompt", prompt,
        "--workspace", str(cell_ws),
        "--timeout", str(timeout),
        "--out", str(cell_dir / "agent-results"),
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 60,
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as e:
        exit_code = 124
        stdout = (e.stdout or b"").decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = "TimeoutExpired in run.py wrapper"

    elapsed = time.time() - t0
    log_end = proxy_log_size()
    proxy_entries = slice_proxy_log(log_start, log_end)

    (cell_dir / "stdout.log").write_text(stdout)
    (cell_dir / "stderr.log").write_text(stderr)
    with open(cell_dir / "proxy.jsonl", "w") as f:
        for e in proxy_entries:
            f.write(json.dumps(e) + "\n")

    summary = {
        "wallet": wallet,
        "agent": agent,
        "test_id": test_id,
        "category": category,
        "started_at": started_at,
        "elapsed_seconds": elapsed,
        "exit_code": exit_code,
        "proxy_entries_count": len(proxy_entries),
        "log_byte_range": [log_start, log_end],
    }
    (cell_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main():
    p = argparse.ArgumentParser(description="Run the agentic wallet benchmark.")
    p.add_argument("--wallets", help="Comma-separated wallet names. Default: all.")
    p.add_argument("--agents", help=f"Comma-separated agent names. Default: {','.join(DEFAULT_AGENTS)}.")
    p.add_argument("--tests", help="Comma-separated test IDs. Default: all 31.")
    p.add_argument("--timeout", type=int, default=180, help="Per-cell timeout (seconds).")
    p.add_argument("--run-id", default=None, help="Run identifier. Defaults to UTC timestamp.")
    p.add_argument("--results-dir", default=None, help="Override results root.")
    args = p.parse_args()

    run_id = args.run_id or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_root = Path(args.results_dir or (BENCH_DIR / "results" / run_id))
    out_root.mkdir(parents=True, exist_ok=True)

    template = (BENCH_DIR / "template.txt").read_text()

    all_tests = discover_tests()
    if args.tests:
        wanted = set(args.tests.split(","))
        all_tests = [t for t in all_tests if t[0] in wanted]

    wallets = args.wallets.split(",") if args.wallets else discover_wallets()
    agents = args.agents.split(",") if args.agents else DEFAULT_AGENTS

    print(f"[run] run_id={run_id}")
    print(f"[run] wallets={wallets}")
    print(f"[run] agents={agents}")
    print(f"[run] tests={len(all_tests)}")

    summaries = []
    for wallet in wallets:
        for agent in agents:
            if wallet == "phantom-mcp" and agent not in MCP_CAPABLE_AGENTS:
                print(f"[skip] {wallet} × {agent}: agent does not speak MCP")
                continue
            for test_id, category, prompt_path in all_tests:
                print(f"[run] {wallet} × {agent} × {test_id}")
                s = run_cell(
                    wallet, agent, test_id, category, prompt_path,
                    template, out_root, args.timeout,
                )
                summaries.append(s)
                print(f"      exit={s['exit_code']} entries={s['proxy_entries_count']} {s['elapsed_seconds']:.1f}s")

    with open(out_root / "index.json", "w") as f:
        json.dump(summaries, f, indent=2)
    print(f"[run] wrote {len(summaries)} cell summaries → {out_root}/index.json")


if __name__ == "__main__":
    sys.exit(main())
