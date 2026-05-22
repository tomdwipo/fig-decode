#!/usr/bin/env bash
# fig-decode skill — one-line installer from GitHub.
#
# Usage (curl-piped, no clone needed):
#   curl -fsSL https://raw.githubusercontent.com/tomdwipo/fig-decode/main/install.sh | bash
#
# Or after cloning:
#   ./install.sh
#
# Installs to ~/.claude/skills/fig-decode/ so Claude Code auto-discovers it.

set -euo pipefail

REPO_URL="https://github.com/tomdwipo/fig-decode.git"
SKILL_DIR="$HOME/.claude/skills/fig-decode"

# If invoked from inside the cloned repo, use local files. Otherwise clone fresh.
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]:-$0}" )" &> /dev/null && pwd || true )"
if [[ -f "$SCRIPT_DIR/decode.js" && -f "$SCRIPT_DIR/decode.sh" ]]; then
    SRC_DIR="$SCRIPT_DIR"
    echo "[fig-decode] using local files at $SRC_DIR"
else
    SRC_DIR="$(mktemp -d)"
    echo "[fig-decode] cloning $REPO_URL → $SRC_DIR"
    command -v git >/dev/null || { echo "ERROR: git required" >&2; exit 1; }
    git clone --depth 1 --quiet "$REPO_URL" "$SRC_DIR"
fi

mkdir -p "$SKILL_DIR/scripts"

# Copy the 6 skill files.
cp "$SRC_DIR/SKILL.md"               "$SKILL_DIR/SKILL.md"
cp "$SRC_DIR/decode.sh"              "$SKILL_DIR/decode.sh"
cp "$SRC_DIR/decode.js"              "$SKILL_DIR/decode.js"
cp "$SRC_DIR/package.json"           "$SKILL_DIR/package.json"
cp "$SRC_DIR/kiwi.py"                "$SKILL_DIR/kiwi.py"
cp "$SRC_DIR/scripts/find_node.py"   "$SKILL_DIR/scripts/find_node.py"
chmod +x "$SKILL_DIR/decode.sh" "$SKILL_DIR/scripts/find_node.py"

# Clean up scratch clone if we made one.
if [[ "$SRC_DIR" != "$SCRIPT_DIR" ]]; then
    rm -rf "$SRC_DIR"
fi

echo
echo "✅ fig-decode skill installed at $SKILL_DIR"
echo
echo "Files written:"
ls -la "$SKILL_DIR"
echo
echo "Files in scripts/:"
ls -la "$SKILL_DIR/scripts"
echo
echo "Dependency check:"
if command -v node  >/dev/null; then echo "  ✅ node  $(node --version)"; else echo "  ❌ node 18+ missing"; fi
if command -v zstd  >/dev/null; then echo "  ✅ zstd  $(zstd --version | head -1 | awk '{print $5}')"; else echo "  ❌ zstd missing — run: brew install zstd"; fi
if command -v unzip >/dev/null; then echo "  ✅ unzip"; else echo "  ❌ unzip missing"; fi
echo
echo "Next steps:"
echo "  1. Decode a .fig:"
echo "     $SKILL_DIR/decode.sh \"\$HOME/Downloads/foo.fig\""
echo
echo "  2. Look up a Figma URL node-id:"
echo "     $SKILL_DIR/scripts/find_node.py 52502-42168"
echo
echo "  3. Or in Claude Code, just say:  /fig-decode <path/to/foo.fig>"
echo "     (the skill auto-loads from ~/.claude/skills/ in every Claude session)"
