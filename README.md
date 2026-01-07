# Portfolio Decision Agent (v1)

This v1 agent is a rules engine for your Fidelity portfolio. It does **not** predict prices and it does **not** auto-trade.
It reads a Fidelity Positions export (CSV), calculates position weights, compares them to your target ranges, and outputs a
one-page Markdown report with suggested actions: **ADD**, **HOLD**, **TRIM**, or **REVIEW**.

## Files
- `agent.py` — the script
- `targets.json` — your target allocation config (edit this as your strategy evolves)
- `sample_run.md` — an example output format
- `system_notes.md` — a markdown reference for Steps 1–4

## Quick start
1. Put your Fidelity CSV somewhere (example: `Positions_All_Accounts.csv`)
2. Edit `targets.json` if you want to change target ranges
3. Run:

```bash
python agent.py --csv Positions_All_Accounts.csv --config targets.json --out report.md
```

Open `report.md`.

## Notes about Fidelity CSVs
Fidelity exports often include a multi-line title block before the header row. This script finds the header row starting with
`Symbol,` and reads rows until the footer (`Totals`, `Disclosure`, etc.).
