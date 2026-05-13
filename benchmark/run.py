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
import atexit
import concurrent.futures
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from datetime import datetime


BENCH_DIR = Path(__file__).parent.resolve()
REPO_DIR = BENCH_DIR.parent
AGENT_RUN = REPO_DIR / "agent-run"

# Pin every URL the benchmarked agents care about to the local proxy. The
# shell that launches run.py may have a different ANTHROPIC_BASE_URL set
# (e.g. pointing at a host-side llmproxy at `localhost:NNNN`) — that value
# is meaningless inside the docker containers, where `localhost` is the
# container itself. Override unconditionally. Keys that aren't a URL get
# setdefault treatment so caller-supplied keys still win.
_URL_OVERRIDES = {
    "LOG_FILE": "/tmp/proxy.jsonl",
    "ANTHROPIC_BASE_URL": "http://host.docker.internal:7777/claude",
    "OPENAI_BASE_URL": "http://host.docker.internal:7777/openai/v1",
    "OPENAI_HOST": "http://host.docker.internal:7777/openai",
    "PI_BASE_URL": "http://host.docker.internal:7777/openai/v1",
}
_KEY_DEFAULTS = {
    "ANTHROPIC_API_KEY": "sk-1234123412341234123412341234123412341234",
    "OPENAI_API_KEY": "sk-1234123412341234123412341234123412341234",
    "GOOSE_PROVIDER": "openai",
    "GOOSE_MODEL": "deepseek-chat",
    "PI_MODEL": "deepseek-chat",
}
for _k, _v in _URL_OVERRIDES.items():
    if os.environ.get(_k) != _v and os.environ.get(_k):
        print(f"[run] overriding {_k} ('{os.environ[_k]}' → '{_v}')", file=sys.stderr)
    os.environ[_k] = _v
for _k, _v in _KEY_DEFAULTS.items():
    os.environ.setdefault(_k, _v)

PROXY_LOG = Path(os.environ["LOG_FILE"])


# Agents in agent-run's AGENTS dict that are wired up against the proxy.
# Skip gemini (removed) and any agent that can't speak through the proxy.
DEFAULT_AGENTS = [
    "claude-code", "codex", "goose", "pi",
]

# phantom-mcp is exposed via an MCP server, but every agent can also shell out
# to the `phantom` CLI in the workspace directly. We let every agent try —
# claude-code uses MCP via .mcp.json; the others fall through to bash and
# invoke `phantom` like any other wallet CLI. No filter applied.

# Wallets whose in-container CLI is a thin shim that forwards to a host-side
# proxy. The benchmark spawns these proxies before running any of their cells
# and tears them down on exit. Keyed by wallet → path to the proxy script.
HOST_PROXIES = {
    "awal": (BENCH_DIR / "wallets" / "awal" / "host-awal-proxy.py", 7788),
}


def _port_in_use(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def ensure_host_proxies(wallets: list[str]) -> None:
    """Start any required host-side proxies for the selected wallets. If a
    proxy is already listening on its port, reuse it. Spawned proxies are
    killed on interpreter exit."""
    for wallet in wallets:
        if wallet not in HOST_PROXIES:
            continue
        script, port = HOST_PROXIES[wallet]
        if _port_in_use(port):
            print(f"[run] {wallet} host proxy already running on :{port}")
            continue
        log_path = Path(f"/tmp/{wallet}-host-proxy.log")
        log_fh = open(log_path, "w")
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            stdout=log_fh, stderr=subprocess.STDOUT,
        )
        # Wait up to ~2s for the listener to bind.
        for _ in range(20):
            if _port_in_use(port):
                break
            time.sleep(0.1)
        else:
            proc.terminate()
            raise RuntimeError(
                f"{wallet} host proxy failed to bind :{port} — see {log_path}"
            )
        print(f"[run] started {wallet} host proxy pid={proc.pid} (log: {log_path})")
        atexit.register(_stop_proc, proc)


def _stop_proc(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def discover_tests() -> list[tuple[str, str, Path]]:
    """Return (test_id, category, prompt_path) for every test folder.

    Each test lives at tests/<category>/<id>/{prompt.txt, criteria.md}.
    """
    out = []
    for cat_dir in sorted((BENCH_DIR / "tests").iterdir()):
        if not cat_dir.is_dir():
            continue
        for test_dir in sorted(cat_dir.iterdir()):
            if not test_dir.is_dir():
                continue
            prompt = test_dir / "prompt.txt"
            if prompt.exists():
                out.append((test_dir.name, cat_dir.name, prompt))
    return out


def discover_wallets() -> list[str]:
    return sorted(d.name for d in (BENCH_DIR / "wallets").iterdir() if d.is_dir())


def build_prompt(template: str, wallet: str, task: str) -> str:
    """If a wallet directory has its own template.txt, use that (lets us
    swap the intro for wallets whose surface area differs from a plain CLI —
    e.g., phantom-mcp's MCP server). Otherwise use the shared default."""
    wallet_template = BENCH_DIR / "wallets" / wallet / "template.txt"
    if wallet_template.exists():
        template = wallet_template.read_text()
    return template.replace("{{WALLET_SDK}}", wallet).replace("{{TASK}}", task)


def proxy_log_size() -> int:
    try:
        return PROXY_LOG.stat().st_size
    except FileNotFoundError:
        return 0


def slice_proxy_log(start: int, end: int, marker: str | None = None) -> list[dict]:
    """Read proxy log bytes in [start, end] and return JSON entries. When a
    `marker` is given, keep only entries whose first user message contains
    that marker — necessary when multiple cells run concurrently and their
    proxy entries interleave in the shared log."""
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
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if marker is not None:
            # Different agents place the cell prompt in different positions —
            # codex/goose put a system prompt at messages[0] and bury the
            # user prompt later. Search every message (and the system field,
            # which some clients also use) for the marker.
            body = entry.get("client_request_body") or {}
            haystack_parts = [json.dumps(body.get("messages") or [])]
            sysf = body.get("system")
            if sysf is not None:
                haystack_parts.append(json.dumps(sysf))
            if marker not in "".join(haystack_parts):
                continue
        out.append(entry)
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
    base_prompt = build_prompt(template, wallet, task)

    # Embed a unique cell marker so we can re-identify this cell's entries in
    # a shared proxy log when wallets run concurrently. The marker lands in
    # the first user message, which every subsequent request re-sends, so it
    # appears in every entry for this cell.
    cell_marker = f"bench-cell-{uuid.uuid4().hex[:12]}"
    prompt = f"<!-- {cell_marker} -->\n\n{base_prompt}"
    (cell_dir / "prompt.txt").write_text(prompt)

    # Per-cell workspace: clone the wallet's template workspace.
    template_ws = wallet_dir / "workspace"
    cell_ws = cell_dir / "workspace"
    if template_ws.exists():
        shutil.copytree(template_ws, cell_ws, dirs_exist_ok=True, symlinks=True)
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
    proxy_entries = slice_proxy_log(log_start, log_end, marker=cell_marker)

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
    # When stdout is piped, Python block-buffers it and our prints land long
    # after subprocess output. Switch to line buffering so run/grade/report
    # output stays in chronological order.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass

    p = argparse.ArgumentParser(description="Run the agentic wallet benchmark.")
    p.add_argument("--wallets", help="Comma-separated wallet names. Default: all.")
    p.add_argument("--agents", help=f"Comma-separated agent names. Default: {','.join(DEFAULT_AGENTS)}.")
    p.add_argument("--tests", help="Comma-separated test IDs. Default: all 31.")
    p.add_argument("--timeout", type=int, default=180, help="Per-cell timeout (seconds).")
    p.add_argument("--run-id", default=None, help="Run identifier. Defaults to UTC timestamp.")
    p.add_argument("--results-dir", default=None, help="Override results root.")
    p.add_argument("--grade", action="store_true",
                   help="Run grade.py after all cells finish.")
    p.add_argument("--report", action="store_true",
                   help="Print a markdown results table after grading (implies --grade).")
    p.add_argument("--judge-timeout", type=int, default=180,
                   help="Per-cell timeout for the grading judge (seconds).")
    p.add_argument("--wallet-parallelism", type=int, default=5,
                   help="How many wallets to run concurrently. Cells within a wallet stay sequential to avoid stomping on shared wallet state.")
    p.add_argument("--grade-parallelism", type=int, default=8,
                   help="How many cells to grade in parallel (each grade spawns a claude-code judge container).")
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

    ensure_host_proxies(wallets)

    summaries: list[dict] = []
    summaries_lock = threading.Lock()
    print_lock = threading.Lock()

    def run_wallet(wallet: str) -> None:
        wallet_ws = BENCH_DIR / "wallets" / wallet / "workspace"
        if not wallet_ws.exists():
            with print_lock:
                print(f"[skip] {wallet}: workspace/ missing — set it up per wallets/{wallet}/README.md")
            return
        for agent in agents:
            for test_id, category, prompt_path in all_tests:
                with print_lock:
                    print(f"[run] {wallet} × {agent} × {test_id}")
                s = run_cell(
                    wallet, agent, test_id, category, prompt_path,
                    template, out_root, args.timeout,
                )
                with summaries_lock:
                    summaries.append(s)
                with print_lock:
                    print(f"      {wallet} × {agent} × {test_id}: exit={s['exit_code']} entries={s['proxy_entries_count']} {s['elapsed_seconds']:.1f}s")

    parallelism = max(1, min(args.wallet_parallelism, len(wallets)))
    print(f"[run] wallet parallelism = {parallelism}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallelism) as pool:
        list(pool.map(run_wallet, wallets))

    # Stable order in index.json regardless of completion order.
    summaries.sort(key=lambda s: (s["wallet"], s["agent"], s["test_id"]))
    with open(out_root / "index.json", "w") as f:
        json.dump(summaries, f, indent=2)
    print(f"[run] wrote {len(summaries)} cell summaries → {out_root}/index.json")

    if args.grade or args.report:
        print(f"[run] grading {len(summaries)} cells (judge timeout {args.judge_timeout}s, parallelism {args.grade_parallelism})…")
        rc = subprocess.call([
            sys.executable, str(BENCH_DIR / "grade.py"),
            "--run-id", run_id,
            "--judge-timeout", str(args.judge_timeout),
            "--parallelism", str(args.grade_parallelism),
        ])
        if rc != 0:
            print(f"[run] grade.py exited {rc}; skipping report")
            return rc

    if args.report:
        print()
        subprocess.call([
            sys.executable, str(BENCH_DIR / "report.py"),
            "--run-id", run_id,
        ])


if __name__ == "__main__":
    sys.exit(main())
