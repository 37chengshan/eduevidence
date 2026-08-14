#!/usr/bin/env bash
# make_upload.sh - build the competition upload/ folder (see packaging/upload-layout.md)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UPLOAD="$ROOT/upload"
EXCLUDE=(
  ".venv" ".git" ".pytest_cache" "__pycache__" "build" "dist"
  "*.egg-info" ".DS_Store" "docs/competition-brief.md" "runs" "upload"
)

echo "==> Building upload folder at $UPLOAD"
rm -rf "$UPLOAD"
mkdir -p "$UPLOAD"

# skill.md (competition-required name; content identical to SKILL.md)
cp "$ROOT/SKILL.md" "$UPLOAD/skill.md"

# source tree (src/)
mkdir -p "$UPLOAD/src"
for d in engine scripts retrieval integrations schemas skill references visualization packaging; do
  rsync -a --exclude-from=<(printf "%s\n" "${EXCLUDE[@]}") "$ROOT/$d" "$UPLOAD/src/"
done
for f in eduevidence_cli.py install.sh pyproject.toml; do
  cp "$ROOT/$f" "$UPLOAD/src/"
done

# top-level materials
cp "$ROOT/LICENSE" "$UPLOAD/LICENSE"
cp "$ROOT/README.md" "$UPLOAD/README.md"
cp "$ROOT/README.en.md" "$UPLOAD/README.en.md"
cp -r "$ROOT/examples" "$UPLOAD/examples"
cp -r "$ROOT/docs" "$UPLOAD/docs"
cp -r "$ROOT/benchmarks" "$UPLOAD/benchmarks"
cp -r "$ROOT/assets" "$UPLOAD/assets"
cp "$ROOT/CHANGELOG.md" "$UPLOAD/CHANGELOG.md"
cp "$ROOT/packaging/UPLOAD-README.md" "$UPLOAD/UPLOAD-README.md"

# exclude leaks again
find "$UPLOAD" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$UPLOAD" -name "*.pyc" -delete 2>/dev/null || true
find "$UPLOAD" -name ".DS_Store" -delete 2>/dev/null || true
rm -f "$UPLOAD/docs/competition-brief.md"

echo "==> Upload folder ready at $UPLOAD"
du -sh "$UPLOAD"
echo "==> Top-level layout:"
ls -la "$UPLOAD" | head -20