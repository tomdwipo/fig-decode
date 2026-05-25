---
name: fig-decode
description: Decode a Figma .fig file or FigJam .jam file (format v100+) into a structured JSON node tree so questions like "what's at node 52502:42168?" can be answered without opening Figma. Useful for design auditing, Figma→code traceability, and PRD/Figma cross-checks when the design lives only as a local export.
metadata:
  author: Tommy Dwi Putranto
  keywords:
  - figma
  - figjam
  - fig-kiwi
  - fig-jam
  - kiwi-schema
  - design-system
  - figma-decode
  - figma-node
  - node-id
---

## When to use

Invoke this skill when a user:

- Provides a path to a `.fig` (Figma Design) or `.jam` (FigJam) file on disk and asks to "look inside" / "explain" / "list pages" / "find a screen".
- Pastes a Figma URL like `https://www.figma.com/design/<file-key>/...?node-id=NNNN-NNNN` or `https://www.figma.com/board/<file-key>/...?node-id=NNNN-NNNN` **and** the corresponding `.fig`/`.jam` is available locally — translate the URL's `node-id` to `NNNN:NNNN` (replace `-` with `:`) and look it up.
- Asks "which screen in code corresponds to Figma node X?" — combine the decoded structure with a grep over the codebase.

**Do not** invoke this skill if the file is only accessible via the Figma cloud — use `mcp__figma__*` tools for those (they need an API token and the file's cloud URL).

### `.fig` vs `.jam`

Both containers use the same Kiwi binary layout (8-byte magic + u32 version + length-prefixed chunks), so the same decoder handles both. The only difference is the 8-byte magic at offset 0: `fig-kiwi` for Figma Design exports, `fig-jam.` for FigJam exports. The skill detects the container at runtime and logs which one it saw. FigJam files yield FigJam-shaped node types (`SHAPE_WITH_TEXT`, `CONNECTOR`, `STICKY`, `SECTION`, `TABLE`) instead of `FRAME`/`COMPONENT`/`INSTANCE` heavy trees.

## Requirements

The decoder runs entirely locally:

- `node` 18+ (uses `npm install` to fetch `kiwi-schema` and `pako` on first run)
- `zstd` CLI (`brew install zstd` on macOS — Figma `.fig` v100+ uses zstd for the document payload)
- `unzip` (system-default)

## How to invoke

The pipeline lives in the same directory as this SKILL.md. From anywhere:

```bash
~/.claude/skills/fig-decode/decode.sh "/path/to/file.fig"   # Figma Design
~/.claude/skills/fig-decode/decode.sh "/path/to/file.jam"   # FigJam
# → prints the output directory it wrote to, defaults to $TMPDIR/fig-decode-<basename>
```

Pass `--full` if the user wants the entire decoded message tree (large — every NodeChange with all 590 fields). Default mode writes only the lightweight `nodes-summary.json` (one record per NodeChange: `{guid, parent, type, name, phase}`).

## How a node-id maps to the output

Figma URLs encode node ids as `NNNN-NNNN`. The same id appears in the decoded tree as a GUID `{sessionID: NNNN, localID: NNNN}`. Use the helper:

```bash
~/.claude/skills/fig-decode/scripts/find_node.py 52502-42168
# → prints the matched node, its parent chain back to the canvas/document, and direct children
```

Without `--out`, the helper picks the most recently decoded `fig-decode-*` directory in `$TMPDIR`.

## Pipeline outputs

```
$TMPDIR/fig-decode-<basename>/
├── canvas.fig          inner Kiwi binary (unzipped from outer .fig archive)
├── meta.json           outer archive metadata
├── thumbnail.png       embedded preview
├── images/             bundled raster assets the design references
├── schema.bin          DEFLATE-decompressed Kiwi schema chunk
├── schema.txt          human-readable schema (`prettyPrintSchema` output)
├── document.bin        zstd-decompressed Kiwi message stream
├── nodes-summary.json  [{guid, parent, type, name, phase}] for every NodeChange
├── stats.json          message/node counts, type histogram, page names
└── message-full.json   only with --full (large)
```

## Limits

- The decoder does not (yet) extract pixel-level visual properties (positions, fills, strokes, fonts). `nodes-summary.json` is the **structural** tree only. To get visual properties, pass `--full` to dump the entire decoded message tree.
- Decoded message tree is ~5-10× the size of the original `.fig`. A 250 MB `.fig` produces a 1+ GB JSON if `--full` is passed. Output goes to `$TMPDIR` by default; pass `--out=` to redirect.
- Re-running on the same `.fig` overwrites the same `$TMPDIR/fig-decode-<basename>/` (idempotent).
