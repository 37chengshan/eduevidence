#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="${DIST_DIR:-$ROOT/dist/eduevidence-submission}"
STAGING="${STAGING_DIR:-$(mktemp -d)}"

echo "==> Staging flat skill package at $STAGING"
rm -rf "$STAGING"
mkdir -p "$STAGING"

cp "$ROOT/SKILL.md" "$STAGING/SKILL.md"

# Runtime + vNext self-evolution control plane. Benchmarks/tests remain excluded.
for d in agents engine domains scripts retrieval integrations schemas skill references autoevolve; do
  test -d "$ROOT/$d" || { echo "missing allowlist dir: $d"; exit 1; }
  rsync -a --exclude={".venv","__pycache__","*.pyc",".DS_Store","runs"} "$ROOT/$d/" "$STAGING/$d/"
done
for f in eduevidence_cli.py install.sh pyproject.toml LICENSE CHANGELOG.md; do
  test -f "$ROOT/$f" || { echo "missing allowlist file: $f"; exit 1; }
  cp "$ROOT/$f" "$STAGING/$f"
done

mkdir -p "$STAGING/visualization"
rsync -a --exclude={".venv","__pycache__","*.pyc",".DS_Store"} \
  "$ROOT/visualization/eduevidence-report/" "$STAGING/visualization/eduevidence-report/"

mkdir -p "$STAGING/web/js"
cp "$ROOT/web/index.html" "$STAGING/web/index.html"
cp "$ROOT/web/styles.css" "$STAGING/web/styles.css"
for f in main.js state.js api.js charts.js dashboard.js viz.js; do
  test -f "$ROOT/web/js/$f" || { echo "missing allowlist web/js/$f"; exit 1; }
  cp "$ROOT/web/js/$f" "$STAGING/web/js/$f"
done

mkdir -p "$STAGING/examples"
for d in ai-coding-assistant-evidence; do
  test -d "$ROOT/examples/$d" || { echo "missing flagship example: $d"; exit 1; }
  rsync -a --exclude={".venv","__pycache__","*.pyc",".DS_Store","figures"} \
    "$ROOT/examples/$d/" "$STAGING/examples/$d/"
done
for d in highschool-math-ai-tutor esl-academic-writing-ai ai-tutor ai-writing-assistant; do
  test -d "$ROOT/examples/$d" || continue
  mkdir -p "$STAGING/examples/$d"
  for f in result.json result.zh.json evidence_graph.json report_spec.json EduEvidence_Report.html; do
    test -f "$ROOT/examples/$d/$f" && cp "$ROOT/examples/$d/$f" "$STAGING/examples/$d/$f"
  done
  test -d "$ROOT/examples/$d/reports-5themes" && \
    rsync -a --exclude={"*.png","*.pdf"} "$ROOT/examples/$d/reports-5themes/" \
      "$STAGING/examples/$d/reports-5themes/"
done

mkdir -p "$STAGING/docs"
for f in architecture.md demo.md demo-storyboard.md install-guide.md \
         reproducibility.md release-contract.md autoresearch-evolution-plan.md \
         orchestration-role-model.md autoresearch-implementation-status.md; do
  test -f "$ROOT/docs/$f" && cp "$ROOT/docs/$f" "$STAGING/docs/$f"
done
cp "$ROOT/packaging/UPLOAD-README.md" "$STAGING/UPLOAD-README.md"
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
        "visualization/lieflat-charts", "benchmarks/", "tests/", "assets/",
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
