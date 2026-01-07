param(
  [Parameter(Mandatory=$true)]
  [string]$Csv
)

$ErrorActionPreference = "Stop"

$month = Get-Date -Format "yyyy-MM"
$out = "reports\$month.md"

python agent.py --csv $Csv --config targets.json --thesis thesis.md --out $out

Write-Host "Wrote report to $out"
