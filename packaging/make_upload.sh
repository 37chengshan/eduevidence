#!/usr/bin/env bash
# make_upload.sh - build the competition upload/ folder as a FLAT SKILL package.
# Only the UPPERCASE SKILL.md is kept at the root (per project decision); the
# layout mirrors the previous dist/eduevidence-submission structure.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UPLOAD="${UPLOAD_DIR:-$ROOT/upload}"

echo "==> Building flat skill upload folder at $UPLOAD"
rm -rf "$UPLOAD"
mkdir -p "$UPLOAD"

# 1) SKILL.md at the root (competition skill document, uppercase only)
cp "$ROOT/SKILL.md" "$UPLOAD/SKILL.md"

# 2) skill resource dirs at the root (flat skill layout)
for d in engine domains scripts retrieval integrations schemas skill references visualization packaging; do
  rsync -a --exclude={".venv","__pycache__","*.pyc",".DS_Store"} "$ROOT/$d" "$UPLOAD/"
done
for f in eduevidence_cli.py install.sh pyproject.toml; do
  cp "$ROOT/$f" "$UPLOAD/"
done

# 3) materials
cp "$ROOT/LICENSE" "$UPLOAD/LICENSE"
cp "$ROOT/README.md" "$UPLOAD/README.md"
cp "$ROOT/README.en.md" "$UPLOAD/README.en.md"
cp "$ROOT/CHANGELOG.md" "$UPLOAD/CHANGELOG.md"
cp -r "$ROOT/examples" "$UPLOAD/examples"
cp -r "$ROOT/docs" "$UPLOAD/docs"
cp -r "$ROOT/benchmarks" "$UPLOAD/benchmarks"
cp -r "$ROOT/assets" "$UPLOAD/assets"
cp -r "$ROOT/tests" "$UPLOAD/tests"
cp "$ROOT/packaging/UPLOAD-README.md" "$UPLOAD/UPLOAD-README.md"
cp "$ROOT/packaging/scp-manifest.json" "$UPLOAD/scp-manifest.json"
cp "$ROOT/packaging/upload-layout.md" "$UPLOAD/upload-layout.md"

# 4) leak cleanup
find "$UPLOAD" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$UPLOAD" -name "*.pyc" -delete 2>/dev/null || true
find "$UPLOAD" -name ".DS_Store" -delete 2>/dev/null || true
rm -f "$UPLOAD/docs/competition-brief.md"
rm -rf "$UPLOAD/docs/superpowers"
rm -rf "$UPLOAD/examples/ai-coding-assistant/reports-5themes_副本"
rm -rf "$UPLOAD/benchmarks/baselines"
rm -rf "$UPLOAD/packaging"

echo "==> Flat skill upload folder ready:"
ls "$UPLOAD"
du -sh "$UPLOAD"