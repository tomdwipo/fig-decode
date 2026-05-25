#!/usr/bin/env bash
# Decode a Figma .fig or FigJam .jam file into a JSON node tree.
#
# Usage:
#   ./decode.sh <path/to/file.fig|.jam> [--out=DIR] [--full]
#
# Requires: node 18+, zstd, unzip. First run installs npm deps locally.

set -euo pipefail

SKILL_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SKILL_DIR"

if [[ $# -lt 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    echo "Usage: $0 <file.fig|.jam> [--out=DIR] [--full]" >&2
    exit 2
fi

command -v node  >/dev/null || { echo "ERROR: node 18+ required" >&2; exit 1; }
command -v zstd  >/dev/null || { echo "ERROR: zstd CLI required (brew install zstd)" >&2; exit 1; }
command -v unzip >/dev/null || { echo "ERROR: unzip required" >&2; exit 1; }

if [[ ! -d node_modules ]]; then
    echo "[fig-decode] first-run: npm install" >&2
    npm install --silent
fi

exec node decode.js "$@"
