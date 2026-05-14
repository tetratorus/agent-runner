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


def _cell_glyph(c: dict | None) -> str:
    if c is None:
        return "—"
    if c.get("skipped"):
        return "N/A"
    glyph = "✓" if c.get("pass") else "✗"
    n = c.get("passes_count", 0) or 0
    if n <= 1:
        return glyph
    # Multi-pass: append pass-count/total so readers can see judge variance
    # at a glance. Example: "✓ 4/5" means 4 of 5 judges said pass.
    pc = c.get("pass_count", 0) or 0
    fc = c.get("fail_count", 0) or 0
    if c.get("pass"):
        return f"{glyph} {pc}/{pc+fc}"
    return f"{glyph} {fc}/{pc+fc}"


def render_markdown(grades: list[dict]) -> str:
    agents = sorted({g["agent"] for g in grades})
    cells = {(g["test_id"], g["wallet"], g["agent"]): g for g in grades}
    rows = sorted({(g["test_id"], g["wallet"]) for g in grades})
    multi_pass = any((g.get("passes_count") or 0) > 1 for g in grades)

    out = io.StringIO()
    header = ["Test", "Wallet", *agents]
    out.write("| " + " | ".join(header) + " |\n")
    out.write("|" + "|".join(["---"] * len(header)) + "|\n")
    for (test, wallet) in rows:
        cells_row = [test, wallet]
        for a in agents:
            cells_row.append(_cell_glyph(cells.get((test, wallet, a))))
        out.write("| " + " | ".join(cells_row) + " |\n")

    # Per-agent totals exclude N/A so they aren't penalized for cells they
    # were never asked to run.
    totals = ["**TOTAL**", ""]
    for a in agents:
        ran = [c for (t, w, ag), c in cells.items() if ag == a and not c.get("skipped")]
        passed = sum(1 for c in ran if c.get("pass"))
        totals.append(f"{passed}/{len(ran)}" if ran else "—")
    out.write("| " + " | ".join(totals) + " |\n")

    if multi_pass:
        out.write("\n")
        # Variance summary
        scored = [g for g in grades if not g.get("skipped") and (g.get("passes_count") or 0) > 0]
        if scored:
            unanimous = sum(1 for g in scored if (g.get("agreement", 1.0) or 0) >= 0.999)
            avg = sum((g.get("agreement", 0.0) or 0) for g in scored) / len(scored)
            out.write(f"_Multi-pass grading: {unanimous}/{len(scored)} cells unanimous, "
                      f"avg judge agreement = {avg:.2f}._\n")
            split = [g for g in scored if (g.get("agreement", 1.0) or 0) < 0.999]
            if split:
                out.write("\n_Cells where judges disagreed (mode shown above):_\n")
                out.write("| Test | Wallet | Agent | Pass/Fail/Total | Agreement |\n")
                out.write("|---|---|---|---|---|\n")
                for g in sorted(split, key=lambda x: (x.get("agreement", 1), x["wallet"], x["agent"], x["test_id"])):
                    pc = g.get("pass_count", 0); fc = g.get("fail_count", 0); n = pc + fc
                    out.write(f"| {g['test_id']} | {g['wallet']} | {g['agent']} | "
                              f"{pc}/{fc}/{n} | {g.get('agreement', 0):.2f} |\n")
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
            elif c.get("skipped"):
                out.append("N/A")
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
