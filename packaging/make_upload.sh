#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="${DIST_DIR:-$ROOT/dist/eduevidence-submission}"
STAGING="${STAGING_DIR:-$(mktemp -d)}"

# Build projections, never research facts. Node is not required at install time.
python3 "$ROOT/scripts/build_report_variants.py"
test -f "$ROOT/web/studio/index.html" || { echo "missing built Studio; run cd studio && npm ci && npm run build"; exit 1; }
echo "==> Staging flat skill package at $STAGING"
rm -rf "$STAGING"
mkdir -p "$STAGING"

# One runtime allowlist is shared with the host installer and wheel.
python3 "$ROOT/scripts/skill_payload.py" "$ROOT" "$STAGING"

cp "$ROOT/packaging/UPLOAD-README.md" "$STAGING/UPLOAD-README.md"
cp "$ROOT/packaging/START-HERE.md" "$STAGING/START-HERE.md"
cp "$ROOT/packaging/scp-manifest.json" "$STAGING/scp-manifest.json"
cp "$ROOT/packaging/upload-layout.md" "$STAGING/upload-layout.md"
cp "$ROOT/README.md" "$STAGING/README.md"
cp "$ROOT/README.zh-CN.md" "$STAGING/README.zh-CN.md"

find "$STAGING" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGING" -name "*.pyc" -delete 2>/dev/null || true
find "$STAGING" -name ".DS_Store" -delete 2>/dev/null || true
rm -rf "$STAGING/docs/competition-brief.md" "$STAGING/docs/superpowers" \
       "$STAGING/benchmarks/baselines" "$STAGING/.agents" "$STAGING/.mimosa" \
       "$STAGING/autoevolve/runs"

cmp "$ROOT/SKILL.md" "$STAGING/SKILL.md"
test -f "$STAGING/agents/openai.yaml"
while IFS= read -r -d '' py; do
  python3 -m py_compile "$py"
done < <(find "$STAGING" -name "*.py" -print0)
FLAGSHIP="$STAGING/examples/ai-coding-assistant-evidence"
test -f "$FLAGSHIP/result.json"
test -f "$FLAGSHIP/result.zh.json"
test -f "$FLAGSHIP/EduEvidence_Report.html"
test -f "$FLAGSHIP/verdict.json"
find "$STAGING" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGING" -name "*.pyc" -delete 2>/dev/null || true

python3 - "$STAGING" <<'PY'
import hashlib, json, sys
from pathlib import Path
staging = Path(sys.argv[1])
files = sorted(f for f in staging.rglob("*") if f.is_file() and f.name != "submission-manifest.json")
entries = []
for f in files:
    entries.append({"path": f.relative_to(staging).as_posix(),
                    "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                    "bytes": f.stat().st_size})
manifest = {
    "project": "EduEvidence",
    "artifact": "dist/eduevidence-submission",
    "generated_at": __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "file_count": len(entries),
    "total_bytes": sum(e["bytes"] for e in entries),
    "manifest_sha256_policy": "manifest excludes itself",
    "exclusions": [
        ".git", ".venv", "caches", "__pycache__", "*.pyc", ".DS_Store",
        "docs/competition-brief.md", "docs/superpowers", ".agents", ".mimosa",
        "runs/", "autoevolve/runs/", "upload/", "web/landing*", "web/archive_*",
        "web/showcase_v2", "web/js/{wizard,did_sandbox,motion}.js", "web/assets/*",
        "visualization/lieflat-charts", "benchmarks/baselines", "benchmarks/results", "tests/", "assets/ except assets/readme/",
        "examples/*/figures"
    ],
    "files": entries,
}
(staging / "submission-manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
PY

echo "==> Manifest written: $STAGING/submission-manifest.json"
rm -rf "$DIST"
mkdir -p "$(dirname "$DIST")"
cp -a "$STAGING" "$DIST"
rm -rf "$STAGING"
echo "==> Submission ready: $DIST"
echo "    files=$(find "$DIST" -type f | wc -l | tr -d ' ') bytes=$(du -sk "$DIST" | cut -f1)K"
echo "    SKILL.md parity: OK | agents/openai.yaml: OK | flagship artifacts: OK"
