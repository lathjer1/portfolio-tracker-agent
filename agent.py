#!/usr/bin/env python3
"""
Portfolio Decision Agent (v1)

Reads a Fidelity "Positions" CSV export, normalizes positions, computes weights, compares to target ranges,
and writes a Markdown report.

Usage:
  python agent.py --csv Positions_All_Accounts.csv --config targets.json --out report.md
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

EXPECTED_COLS = [
    "Symbol","Quantity","Last","$ Chg","% Chg","Bid","Ask","Volume",
    "$ Avg Cost","$ Day G/L","% Day G/L","$ Total G/L","% Total G/L",
    "Value","Basis","Day Range","52W Range","Earnings Date","Div Amt","Div Ex-Date"
]

FOOTER_PREFIXES = (
    "Totals", "Disclosure", "The data and information", "For more information", "Brokerage services",
    "Both are Fidelity", "\"Both are Fidelity"
)

def parse_thesis_sections(thesis_path: Path) -> set[str]:
    """
    Reads thesis.md and returns a set of symbols that have a '## SYMBOL' section.
    """
    if not thesis_path.exists():
        return set()

    text = thesis_path.read_text(encoding="utf-8", errors="replace").splitlines()
    symbols = set()
    for ln in text:
        ln = ln.strip()
        if ln.startswith("## "):
            sym = ln[3:].strip()
            # Keep it simple: treat the whole heading as symbol/key
            if sym:
                symbols.add(sym)
    return symbols

def _to_float(x: str) -> Optional[float]:
    s = (x or "").strip()
    if s in ("", "--"):
        return None
    s = s.replace("$", "").replace("%", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None

def load_targets(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def read_fidelity_positions(csv_path: Path) -> List[dict]:
    """
    Fidelity exports often include a title block before the real header. We:
    - scan for a line starting with 'Symbol,'
    - read subsequent non-empty lines until a footer
    - parse as CSV rows
    """
    lines = csv_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    header_idx = None
    for i, ln in enumerate(lines):
        if ln.startswith("Symbol,"):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("Could not find header row starting with 'Symbol,' in the provided CSV.")

    data_lines: List[str] = []
    for ln in lines[header_idx + 1:]:
        if not ln.strip():
            continue
        if ln.startswith(FOOTER_PREFIXES):
            break
        data_lines.append(ln)

    rows: List[dict] = []
    for ln in data_lines:
        parts = next(csv.reader([ln]))
        parts = (parts + [""] * len(EXPECTED_COLS))[:len(EXPECTED_COLS)]
        row = dict(zip(EXPECTED_COLS, parts))
        rows.append(row)
    return rows

@dataclass
class Position:
    symbol: str
    qty: float
    last: float
    value: float
    bucket: str = "Unassigned"

def normalize_positions(raw_rows: List[dict], targets: dict) -> List[Position]:
    alias_map: Dict[str, str] = targets.get("alias_map", {})
    cash_symbols = set(s.strip() for s in targets.get("cash_symbols", []))

    positions: List[Position] = []
    for r in raw_rows:
        sym_raw = (r.get("Symbol") or "").strip()
        if not sym_raw:
            continue

        sym = alias_map.get(sym_raw, sym_raw)
        if sym_raw in cash_symbols or "cash" in sym_raw.lower():
            sym = "CASH"

        qty = _to_float(r.get("Quantity", "")) or 0.0
        last = _to_float(r.get("Last", "")) or 0.0
        value = _to_float(r.get("Value", ""))

        if value is None:
            value = qty * last

        positions.append(Position(symbol=sym, qty=qty, last=last, value=value))
    return positions

def build_target_maps(targets: dict) -> Tuple[Dict[str, Tuple[float,float]], Dict[str, Tuple[float,float]]]:
    per_symbol: Dict[str, Tuple[float,float]] = {}
    per_bucket: Dict[str, Tuple[float,float]] = {}
    for bucket_name, bucket in targets["buckets"].items():
        per_bucket[bucket_name] = tuple(bucket["target_total_pct"])
        for sym, rng in bucket["positions"].items():
            per_symbol[sym] = tuple(rng)
    return per_symbol, per_bucket

def assign_buckets(positions: List[Position], targets: dict) -> None:
    sym_to_bucket: Dict[str, str] = {}
    for bucket_name, bucket in targets["buckets"].items():
        for sym in bucket["positions"].keys():
            sym_to_bucket[sym] = bucket_name
    for p in positions:
        p.bucket = sym_to_bucket.get(p.symbol, "Unassigned")

def pct(x: float) -> str:
    return f"{x:.2f}%"

def action_for_position(actual_pct: float, target_rng: Tuple[float,float], hard_cap: float) -> str:
    lo, hi = target_rng
    if actual_pct > hard_cap:
        return "TRIM (concentration)"
    if actual_pct < lo:
        return "ADD"
    if actual_pct > hi:
        return "TRIM"
    return "HOLD"

def make_report(positions: List[Position], targets: dict, thesis_symbols: set[str] | None = None) -> str:
    per_symbol_targets, per_bucket_targets = build_target_maps(targets)
    assign_buckets(positions, targets)

    thesis_symbols = thesis_symbols or set()

    total = sum(p.value for p in positions if p.value is not None)
    if total <= 0:
        raise ValueError("Total portfolio value computed as 0. Check the CSV parsing.")

    hard_caps = targets.get("hard_caps", {})
    single_cap = float(hard_caps.get("single_position_pct", 12))
    spec_cap = float(hard_caps.get("speculation_bucket_pct", 10))

    pos_rows = []
    for p in positions:
        ap = (p.value / total) * 100
        tr = per_symbol_targets.get(p.symbol)
        pos_rows.append((p, ap, tr))

    bucket_totals: Dict[str, float] = {}
    for p in positions:
        bucket_totals[p.bucket] = bucket_totals.get(p.bucket, 0.0) + p.value
    bucket_pcts = {b: (v/total)*100 for b, v in bucket_totals.items()}

    lines: List[str] = []
    lines.append(f"# Portfolio Report — {targets.get('strategy_name','Strategy')}")
    lines.append("")
    lines.append(f"**Total portfolio value:** ${total:,.2f}")
    lines.append("")

    lines.append("## Bucket summary")
    lines.append("")
    lines.append("| Bucket | Actual % | Target % | Status |")
    lines.append("|---|---:|---:|---|")
    for bname, actual in sorted(bucket_pcts.items(), key=lambda x: x[1], reverse=True):
        tr = per_bucket_targets.get(bname)
        if tr:
            status = "OK" if (actual >= tr[0] and actual <= tr[1]) else ("UNDER" if actual < tr[0] else "OVER")
            lines.append(f"| {bname} | {pct(actual)} | {tr[0]:.0f}–{tr[1]:.0f}% | {status} |")
        else:
            lines.append(f"| {bname} | {pct(actual)} | — | — |")

    if "Speculation" in bucket_pcts and bucket_pcts["Speculation"] > spec_cap + 1e-9:
        lines.append("")
        lines.append(f"**Alert:** Speculation bucket is {pct(bucket_pcts['Speculation'])} which is above the cap ({spec_cap:.0f}%).")

    # Thesis coverage
    lines.append("")
    lines.append("## Thesis coverage")
    lines.append("")
    lines.append("| Symbol | Bucket | Thesis? |")
    lines.append("|---|---|---|")

    # Only check non-core + non-cash positions that are in targets
    for p, actual, tr in pos_rows:
        if p.bucket in ("Core", "Cash"):
            continue
        if tr is None:
            # Not in targets: still helpful to have a thesis if you keep it
            has = "✅" if p.symbol in thesis_symbols else "⚠️ missing"
            lines.append(f"| {p.symbol} | {p.bucket} | {has} |")
            continue

        has = "✅" if p.symbol in thesis_symbols else "⚠️ missing"
        lines.append(f"| {p.symbol} | {p.bucket} | {has} |")

    missing = []
    for p, actual, tr in pos_rows:
        if p.bucket in ("Core", "Cash"):
            continue
        if p.symbol not in thesis_symbols:
            missing.append(p.symbol)

    if missing:
        lines.append("")
        lines.append("**Add thesis sections for:** " + ", ".join(sorted(set(missing))))

    lines.append("")
    lines.append("## Position actions")
    lines.append("")
    lines.append("| Symbol | Bucket | Actual % | Target % | Action |")
    lines.append("|---|---|---:|---:|---|")

    pos_rows.sort(key=lambda t: t[1], reverse=True)
    for p, actual, tr in pos_rows:
        if tr is None:
            lines.append(f"| {p.symbol} | {p.bucket} | {pct(actual)} | — | REVIEW (not in targets) |")
            continue
        action = action_for_position(actual, tr, single_cap)
        lines.append(f"| {p.symbol} | {p.bucket} | {pct(actual)} | {tr[0]:.0f}–{tr[1]:.0f}% | {action} |")

    lines.append("")
    lines.append("## Priority list (what to do first)")
    lines.append("")

    priorities: List[str] = []
    core_actual = bucket_pcts.get("Core", 0.0)
    core_target = per_bucket_targets.get("Core")
    if core_target and core_actual < core_target[0]:
        priorities.append(f"- Build **Core**: currently {pct(core_actual)} vs target {core_target[0]:.0f}–{core_target[1]:.0f}%. Route new money and trims primarily to VTI/SCHD.")

    for p, actual, tr in pos_rows:
        if actual > single_cap + 1e-9:
            priorities.append(f"- Reduce concentration: **{p.symbol}** is {pct(actual)} (cap {single_cap:.0f}%).")

    for p, actual, tr in pos_rows:
        if tr and actual > tr[1] + 1e-9 and actual <= single_cap + 1e-9:
            priorities.append(f"- Consider trimming: **{p.symbol}** is {pct(actual)} vs target {tr[0]:.0f}–{tr[1]:.0f}%.")

    for p, actual, tr in pos_rows:
        if tr and actual < tr[0] - 1e-9:
            priorities.append(f"- Candidate to add: **{p.symbol}** is {pct(actual)} vs target {tr[0]:.0f}–{tr[1]:.0f}%.")

    if not priorities:
        priorities.append("- Portfolio is within target ranges. Maintain contributions and review monthly.")

    lines.extend(priorities)
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- This report is decision support, not an instruction to trade. You control execution and timing.")
    return "\\n".join(lines)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to Fidelity Positions CSV export")
    ap.add_argument("--config", required=True, help="Path to targets.json")
    ap.add_argument("--out", required=True, help="Path to write report.md")
    ap.add_argument("--thesis", required=False, help="Path to thesis.md (optional)")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    cfg_path = Path(args.config)
    out_path = Path(args.out)

    targets = load_targets(cfg_path)
    thesis_symbols = set()
    if args.thesis:
        thesis_symbols = parse_thesis_sections(Path(args.thesis))
    raw = read_fidelity_positions(csv_path)
    pos = normalize_positions(raw, targets)
    report = make_report(pos, targets, thesis_symbols=thesis_symbols)
    out_path.write_text(report, encoding="utf-8")
    print(f"Wrote report to: {out_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
