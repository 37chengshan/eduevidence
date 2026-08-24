#!/usr/bin/env bash
# make_upload.sh - build the competition submission folder as a clean allowlist
# staging package: dist/eduevidence-submission/ (never upload/ by default).
#
# The folder is the competition artifact: SKILL.md + runtime source + three-page
# read-only web/ + report renderer + main demo + minimal docs. Everything is
# copied from an explicit allowlist; anything missing from the allowlist fails
# the build. No archives are produced (unless STAGING_DIR points elsewhere the
# caller controls). A submission-manifest.json records file count, bytes and a
# hash per file (manifest excludes itself).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="${DIST_DIR:-$ROOT/dist/eduevidence-submission}"
STAGING="${STAGING_DIR:-$(mktemp -d)}"

echo "==> Staging flat skill package at $STAGING"
rm -rf "$STAGING"
mkdir -p "$STAGING"

# 1) SKILL.md at root (uppercase; lowercase copy is a platform upload decision).
cp "$ROOT/SKILL.md" "$STAGING/SKILL.md"

# 2) Runtime source allowlist (flat skill layout). visualization excludes the
#    upstream lieflat-charts gallery (reference material only, 20 MB).
for d in engine domains scripts retrieval integrations schemas skill references; do
  test -d "$ROOT/$d" || { echo "missing allowlist dir: $d"; exit 1; }
  rsync -a --exclude={".venv","__pycache__","*.pyc",".DS_Store"} "$ROOT/$d/" "$STAGING/$d/"
done
for f in eduevidence_cli.py install.sh pyproject.toml LICENSE CHANGELOG.md; do
  test -f "$ROOT/$f" || { echo "missing allowlist file: $f"; exit 1; }
  cp "$ROOT/$f" "$STAGING/$f"
done

# 3) Report renderer (eduevidence-report) — runtime import closure only.
mkdir -p "$STAGING/visualization"
rsync -a --exclude={".venv","__pycache__","*.pyc",".DS_Store"} \
  "$ROOT/visualization/eduevidence-report/" "$STAGING/visualization/eduevidence-report/"

# 4) Three-page web/ allowlist: entry + styles + the six live modules.
#    Excludes landing/, archive_v*/, showcase_v2/, assets/, wizard/did/motion.
mkdir -p "$STAGING/web/js"
cp "$ROOT/web/index.html" "$STAGING/web/index.html"
cp "$ROOT/web/styles.css" "$STAGING/web/styles.css"
for f in main.js state.js api.js charts.js dashboard.js viz.js; do
  test -f "$ROOT/web/js/$f" || { echo "missing allowlist web/js/$f"; exit 1; }
  cp "$ROOT/web/js/$f" "$STAGING/web/js/$f"
done

# 5) Main demo (ai-coding-assistant) + other runnable examples keep result/report.
mkdir -p "$STAGING/examples"
for d in ai-coding-assistant ai-coding-assistant-evidence; do
  test -d "$ROOT/examples/$d" || continue
  rsync -a --exclude={".venv","__pycache__","*.pyc",".DS_Store","figures"} \
    "$ROOT/examples/$d/" "$STAGING/examples/$d/"
done
# A few extra examples stay but only their artifacts (no generated figures).
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

# 6) Minimal docs (release contract, demo, install) + packaging notes.
mkdir -p "$STAGING/docs"
for f in architecture.md demo.md demo-storyboard.md install-guide.md \
         reproducibility.md release-contract.md; do
  test -f "$ROOT/docs/$f" && cp "$ROOT/docs/$f" "$STAGING/docs/$f"
done
cp "$ROOT/packaging/UPLOAD-README.md" "$STAGING/UPLOAD-README.md"
cp "$ROOT/packaging/scp-manifest.json" "$STAGING/scp-manifest.json"
cp "$ROOT/packaging/upload-layout.md" "$STAGING/upload-layout.md"

# 7) READMEs.
cp "$ROOT/README.md" "$STAGING/README.md"
cp "$ROOT/README.zh-CN.md" "$STAGING/README.zh-CN.md"

# 8) Leak cleanup (defense in depth; allowlist already excludes these).
find "$STAGING" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGING" -name "*.pyc" -delete 2>/dev/null || true
find "$STAGING" -name ".DS_Store" -delete 2>/dev/null || true
rm -rf "$STAGING/docs/competition-brief.md" "$STAGING/docs/superpowers" \
       "$STAGING/examples/ai-coding-assistant/reports-5themes_副本" \
       "$STAGING/benchmarks/baselines" "$STAGING/.agents" "$STAGING/.mimosa"

# 9) Release gates: SKILL.md parity, Python compiles, main demo artifacts.
cmp "$ROOT/SKILL.md" "$STAGING/SKILL.md"
find "$STAGING" -name "*.py" -print0 | xargs -0 -n1 python3 -m py_compile 2>/dev/null
test -f "$STAGING/examples/ai-coding-assistant/result.json"
test -f "$STAGING/examples/ai-coding-assistant/result.zh.json"
test -f "$STAGING/examples/ai-coding-assistant/EduEvidence_Report.html"
# py_compile regenerates __pycache__; drop it again before manifest.
find "$STAGING" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGING" -name "*.pyc" -delete 2>/dev/null || true

# 10) Manifest via python (portable across macOS/Linux; excludes itself).
python3 - "$STAGING" <<'PY'
import hashlib, json, sys
from pathlib import Path
staging = Path(sys.argv[1])
files = sorted(f for f in staging.rglob("*") if f.is_file()
               and f.name != "submission-manifest.json")
entries = []
for f in files:
    rel = f.relative_to(staging).as_posix()
    entries.append({"path": rel,
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
        "runs/", "upload/", "web/landing*", "web/archive_*", "web/showcase_v2",
        "web/js/{wizard,did_sandbox,motion}.js", "web/assets/*",
        "visualization/lieflat-charts", "benchmarks/", "tests/", "assets/",
        "examples/ai-coding-assistant/reports-5themes_副本", "examples/*/figures"
    ],
    "files": entries,
}
(staging / "submission-manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
PY
echo "==> Manifest written: $STAGING/submission-manifest.json"

# 11) Publish to dist (clean swap).
rm -rf "$DIST"
mkdir -p "$(dirname "$DIST")"
cp -a "$STAGING" "$DIST"
rm -rf "$STAGING"

echo "==> Submission ready: $DIST"
echo "    files=$(find "$DIST" -type f | wc -l | tr -d ' ') bytes=$(du -sk "$DIST" | cut -f1)K"
echo "    SKILL.md parity: OK | main demo artifacts: OK"