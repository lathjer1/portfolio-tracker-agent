# Fidelity Portfolio System Notes (Steps 1–4)

## Step 1 — Normalize positions
- Use Fidelity “Positions” export (CSV).
- Parse by finding the header row starting with `Symbol,`.
- Stop reading at footers like `Totals`, `Disclosure`, etc.
- Normalize fields and compute:
  - Market value per holding
  - Portfolio total value
  - Weight (%) per holding
- Bucket each holding (Core / Conviction / Speculation / Cash).

## Step 2 — Target structure (Aggressive Growth)
- Core: 55%
- Conviction satellites: 30%
- Speculation: 10% (hard cap)
- Cash: 5%

## Step 3 — Position-by-position targets (v1)
Core:
- VTI: 40–45%
- SCHD: 10–15%

Conviction:
- AAPL: 7–10%
- MSFT: 7–10%
- KNSL: 5–7%
- JNJ: 3–5%
- O: 2–4%

Speculation:
- RBLX: 2–3%
- RDW: 1–3%
- KALV: 1–2%
- TEM: 1–2%

Cash:
- CASH: 5%

Hard caps:
- Any single position: 12%
- Speculation bucket: 10%

## Step 4 — Rules engine (v1)
- Read Fidelity positions CSV
- Calculate weights
- Compare to target ranges
- Output:
  - Bucket summary
  - Position actions (ADD/HOLD/TRIM/REVIEW)
  - Priority list
