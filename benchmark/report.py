#!/usr/bin/env python3
"""Render a results table from a graded benchmark run.

Reads `results/<run-id>/grades.json` (preferred) or walks per-cell `grade.json`
files as a fallback, and prints a markdown table where rows are (test, wallet)
pairs and columns are agents. A summary row totals passes per agent.

Usage:
    python3 benchmark/report.py --run-id <id>
    python3 benchmark/report.py --run-id <id> --format csv
    python3 benchmark/report.py --run-id <id> --output table.md
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).parent.resolve()


def load_grades(run_dir: Path) -> list[dict]:
    grades_file = run_dir / "grades.json"
    if grades_file.exists():
        return json.loads(grades_file.read_text())
    out = []
    for f in sorted(run_dir.rglob("grade.json")):
        try:
            out.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            pass
    return out


def render_markdown(grades: list[dict]) -> str:
    agents = sorted({g["agent"] for g in grades})
    cells = {(g["test_id"], g["wallet"], g["agent"]): g for g in grades}
    rows = sorted({(g["test_id"], g["wallet"]) for g in grades})

    out = io.StringIO()
    header = ["Test", "Wallet", *agents]
    out.write("| " + " | ".join(header) + " |\n")
    out.write("|" + "|".join(["---"] * len(header)) + "|\n")
    for (test, wallet) in rows:
        cells_row = [test, wallet]
        for a in agents:
            c = cells.get((test, wallet, a))
            if c is None:
                cells_row.append("—")
            elif c.get("pass"):
                cells_row.append("✓")
            else:
                cells_row.append("✗")
        out.write("| " + " | ".join(cells_row) + " |\n")

    # Per-agent totals over the cells that actually ran.
    totals = ["**TOTAL**", ""]
    for a in agents:
        ran = [c for (t, w, ag), c in cells.items() if ag == a]
        passed = sum(1 for c in ran if c.get("pass"))
        totals.append(f"{passed}/{len(ran)}" if ran else "—")
    out.write("| " + " | ".join(totals) + " |\n")
    return out.getvalue()


def render_csv(grades: list[dict]) -> str:
    agents = sorted({g["agent"] for g in grades})
    cells = {(g["test_id"], g["wallet"], g["agent"]): g for g in grades}
    rows = sorted({(g["test_id"], g["wallet"]) for g in grades})

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["test", "wallet", *agents])
    for (test, wallet) in rows:
        out = [test, wallet]
        for a in agents:
            c = cells.get((test, wallet, a))
            if c is None:
                out.append("")
            else:
                out.append("PASS" if c.get("pass") else "FAIL")
        w.writerow(out)
    return buf.getvalue()


def main() -> int:
    p = argparse.ArgumentParser(description="Render a benchmark results table.")
    p.add_argument("--run-id", required=True)
    p.add_argument("--format", default="markdown", choices=["markdown", "csv"])
    p.add_argument("--output", help="Write to this file instead of stdout.")
    args = p.parse_args()

    run_dir = BENCH_DIR / "results" / args.run_id
    if not run_dir.exists():
        print(f"ERROR: {run_dir} not found", file=sys.stderr)
        return 1

    grades = load_grades(run_dir)
    if not grades:
        print(f"ERROR: no grades found under {run_dir} (run grade.py first)", file=sys.stderr)
        return 1

    renderer = render_csv if args.format == "csv" else render_markdown
    text = renderer(grades)

    if args.output:
        Path(args.output).write_text(text)
        print(f"wrote {args.output}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
