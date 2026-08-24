#!/usr/bin/env bash
# bake_pack.sh — Render main + 5-theme HTML reports and refresh artifact
# manifest for one example pack. Usage:
#   bash scripts/bake_pack.sh examples/ai-coding-assistant-evidence
set -euo pipefail

PACK="${1:?usage: bake_pack.sh examples/<pack>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BR="$ROOT/visualization/eduevidence-report/scripts"
PY="${PYTHON:-python3}"

R_EN="$PACK/result.json"
R_ZH="$PACK/result.zh.json"
THEMES_DIR="$PACK/reports-5themes"

test -f "$ROOT/$R_EN" || { echo "missing $R_EN"; exit 1; }
test -f "$ROOT/$R_ZH" || { echo "missing $R_ZH"; exit 1; }
mkdir -p "$ROOT/$THEMES_DIR"

cd "$ROOT"

echo "== main report (claude) =="
"$PY" "$BR/build_report.py" --result "$R_EN" --result-zh "$R_ZH" \
    --out "$PACK/EduEvidence_Report.html"

for t in claude academic datalab datalab-dark presentation; do
  echo "== theme $t =="
  "$PY" "$BR/build_report.py" --result "$R_EN" --result-zh "$R_ZH" \
      --theme "$t" --out "$THEMES_DIR/report_$t.html"
  cp "$THEMES_DIR/report_$t.html" "$THEMES_DIR/EduEvidence_Report_$t.html"
done

echo "== artifact manifest =="
"$PY" "$BR/build_artifact_manifest.py" --result "$R_EN" --result-zh "$R_ZH" \
    --html-dir "$THEMES_DIR" --out "$PACK/artifact_manifest.json"

echo "bake complete: $PACK"
