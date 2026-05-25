# fig-decode

> Decode Figma `.fig` design files **and** FigJam `.jam` board files (format v100+) into a structured JSON node tree — locally, with no Figma cloud access required.

Ships as a [Claude Code](https://claude.com/claude-code) skill **and** a standalone CLI. Lets any developer ask *"what's at Figma node 52502:42168?"* or *"render the flow at FigJam section 7870-221"* without uploading the design to Figma cloud, without an API token, without leaving the terminal.

```bash
# one-line install
curl -fsSL https://raw.githubusercontent.com/tomdwipo/fig-decode/main/install.sh | bash

# decode either container — same script
~/.claude/skills/fig-decode/decode.sh ~/Downloads/your-design.fig
~/.claude/skills/fig-decode/decode.sh ~/Downloads/your-board.jam

# look up a Figma URL node-id (replace - with : or pass either form)
~/.claude/skills/fig-decode/scripts/find_node.py 52502-42168
```

## Why this exists

Figma's `.fig` export is a proprietary binary format. The community OSS parser ([`fig-kiwi@0.0.1`](https://www.npmjs.com/package/fig-kiwi)) targets format **v15**; current Figma exports are **v100+** with two different compression schemes inside (DEFLATE for the schema chunk, **zstd** for the document chunk). Out-of-the-box tooling does not handle this combination.

FigJam `.jam` exports use the **same** Kiwi container layout but stamp a different 8-byte magic (`fig-jam.` instead of `fig-kiwi`) and ship a different schema with whiteboard-shaped node types (`SHAPE_WITH_TEXT`, `CONNECTOR`, `STICKY`, `SECTION`, `TABLE`). The `fig-kiwi` npm package rejects `.jam` files outright on the magic check.

This skill wraps the right combination of decoders so anyone can introspect a design export locally — no Figma cloud account, no API token, no leaking sensitive designs to third-party renderers.

## `.fig` vs `.jam` — same container, different magic byte

| | `.fig` (Figma Design) | `.jam` (FigJam) |
|---|---|---|
| Outer container | ZIP with `canvas.fig` inside | ZIP with `canvas.fig` inside |
| 8-byte magic | `fig-kiwi` | `fig-jam.` (last byte is a sub-version) |
| Schema chunk compression | DEFLATE | DEFLATE |
| Document chunk compression | zstd | zstd |
| Schema | Figma Design types | FigJam types (SHAPE_WITH_TEXT, CONNECTOR, …) |
| URL pattern | `figma.com/design/<key>/...` | `figma.com/board/<key>/...` |

The decoder accepts both (`MAGIC_RE = /^fig-(kiwi|jam\.)/`) and logs which container it saw.

## Install

### Option 1 — One-line (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/tomdwipo/fig-decode/main/install.sh | bash
```

The script clones a fresh copy of this repo into a temp directory, copies 6 files to `~/.claude/skills/fig-decode/`, marks shell scripts executable, verifies dependencies, and prints next-step usage examples.

### Option 2 — Clone + install

```bash
git clone https://github.com/tomdwipo/fig-decode.git
cd fig-decode
./install.sh
```

### Option 3 — Via Claude Code

Open Claude Code in any session and paste:

> install this skill from https://github.com/tomdwipo/fig-decode and teach me how to use it

Claude will fetch the repo, run `install.sh`, verify dependencies, and walk you through the first decode + node lookup on a sample `.fig`.

## Prerequisites

- **Node 18+**
- **`zstd` CLI** — `brew install zstd` on macOS (Figma v100+ uses zstd for the document payload)
- **`unzip`** — built into macOS / standard on Linux

## How to get a `.fig` or `.jam` file

### From Figma Desktop

1. Open the design in Figma Desktop
2. **File → Save local copy…**
3. Save anywhere (e.g. `~/Downloads/My Design.fig` or `~/Downloads/My Board.jam`)

### From Figma Web

1. Open the design at `figma.com/design/<key>/...` (Design) or `figma.com/board/<key>/...` (FigJam)
2. **Top-left menu (hamburger) → File → Save local copy…**
3. Browser downloads `.fig` (Design) or `.jam` (FigJam)

> 💡 The `.fig` / `.jam` is a self-contained file (an outer ZIP archive). Production design files can be 250+ MB. Don't commit them to git — Figma is the source of truth.

## Usage

### Decode a `.fig` or `.jam` file

```bash
~/.claude/skills/fig-decode/decode.sh ~/Downloads/my-design.fig    # Figma Design
~/.claude/skills/fig-decode/decode.sh ~/Downloads/my-board.jam     # FigJam
```

Output goes to `$TMPDIR/fig-decode-<basename>/` by default. Use `--out=DIR` to redirect:

```bash
~/.claude/skills/fig-decode/decode.sh ~/Downloads/my-design.fig --out=~/.cache/fig-decode/my-design
```

Use `--full` to also write `message-full.json` (every NodeChange with all 590 fields — large, ~1+ GB for big files).

### Look up a node by its Figma URL node-id

Figma URLs encode node ids as `NNNN-NNNN`. Replace `-` with `:` and that's the GUID inside the decoded tree. The helper accepts either form:

```bash
~/.claude/skills/fig-decode/scripts/find_node.py 52502-42168
```

Output:

```
FOUND 52502:42168 → [FRAME] ' Results - Failed'

Parent chain (innermost → root):
  [FRAME     ] ' Results - Failed'
  [SECTION   ] ' RESULTS REJECTED'
  [SECTION   ] 'folow '
  [CANVAS    ] '     •  xxx -'
  [DOCUMENT  ] 'Document'

Children (depth 1):
  [INSTANCE] 'Top Bar New'
  [FRAME   ] 'Frame 1000002012'
```

### List all pages (CANVAS nodes)

```bash
jq -r '.pageNames[]' "$TMPDIR/fig-decode-my-design/stats.json"
```

### Count frames matching a pattern

```bash
jq '[.[] | select(.type=="FRAME" and (.name // "" | contains("Token")))] | length' \
   "$TMPDIR/fig-decode-my-design/nodes-summary.json"
```

### Inspect the Kiwi schema

```bash
grep -A20 "^message NodeChange " "$TMPDIR/fig-decode-my-design/schema.txt"
```

## What the decoder produces

```
$TMPDIR/fig-decode-<basename>/
├── canvas.fig          inner Kiwi binary (unzipped from outer .fig archive)
├── meta.json           outer archive metadata
├── thumbnail.png       embedded preview
├── images/             bundled raster assets the design references
├── schema.bin          DEFLATE-decompressed Kiwi schema chunk
├── schema.txt          human-readable schema (605 type definitions)
├── document.bin        zstd-decompressed Kiwi message stream
├── nodes-summary.json  [{guid, parent, type, name, phase}] per NodeChange
├── stats.json          message/node counts, type histogram, page names
└── message-full.json   only with --full (large; entire decoded message tree)
```

For a typical 264 MB `.fig` (Figma format v106):

| Metric | Value |
|---|---|
| Schema definitions | 605 types (enums + structs + messages) |
| Decode time | ~7 seconds (most of that is zstd + Kiwi walk) |
| NodeChange records | ~423,000 |
| Pages (CANVAS) | ~200 |
| `nodes-summary.json` size | ~60 MB |
| `document.bin` size | ~232 MB |

## How decoding works (under the hood)

```
foo.fig (264 MB ZIP archive)        foo.jam (FigJam ZIP archive)
   │                                     │
   ├─ unzip ──> canvas.fig, meta.json, thumbnail.png, images/
   │
   └─ canvas.fig (Kiwi binary, v100+)
        │
        ├─ header: magic (8B) + uint32 version (4B)
        │     magic ∈ {"fig-kiwi", "fig-jam."}    ← only difference between containers
        │
        ├─ chunk[0] (length-prefixed)
        │     └─ pako.inflateRaw  ──> Kiwi schema bytes (~28 KB → 68 KB)
        │              └─ kiwi-schema.decodeBinarySchema  ──> 605 defs
        │                       └─ kiwi-schema.compileSchema  ──> compiled walker
        │
        └─ chunk[1] (length-prefixed, zstd-framed)
              └─ zstd -d  ──> Kiwi message stream
                       └─ compiled.decodeMessage(bb) until EOF  ──> Message[]
                                └─ flatten m.nodeChanges to nodes-summary.json
```

### Non-obvious gotchas

1. **Compression switched mid-stream.** The schema chunk is **DEFLATE**, the document chunk is **zstd**. Older parsers assume both are DEFLATE and fail on v100+. Detect per-chunk by reading the first 4 bytes: `28 b5 2f fd` = zstd, anything else = DEFLATE.

2. **The document is a *stream* of `Message` records, not one big Message.** Loop `compiled.decodeMessage(bb)` until the buffer is exhausted.

3. **`fig-kiwi@0.0.1` on npm only handles v15.** This repo is for v100+ files (current Figma exports).

4. **FigJam magic has a sub-version byte.** The 8-byte magic for FigJam is `fig-jam.` where the last byte is a sub-version (an ASCII `.` for the v106 board we tested; may change). Match with a regex `/^fig-(kiwi|jam\.)/` rather than a string equals. Same Kiwi schema layout otherwise — no separate decoder needed.

5. **FigJam connector graph isn't a parent/child tree.** A single shape can be the target of many connectors and walking `nodes-summary.json` alone won't reconstruct the flow. To render a flow, you need `--full` and to follow `connectorStart.endpointNodeID` → `connectorEnd.endpointNodeID` edges.

## Cross-session context — Claude remembers across chats

> "I decoded a 264 MB `.fig` on Monday. On Wednesday I open a new Claude session — do I have to decode it again?"

**No, as long as the decoded output is still on disk.**

| Asset | Survives reboot? | Survives new Claude session? |
|---|---|---|
| The skill itself (`~/.claude/skills/fig-decode/`) | ✅ | ✅ auto-loaded |
| Decoded outputs in `$TMPDIR/fig-decode-*/` | ❌ macOS clears `/private/tmp` on boot or after 3 days | ✅ if still on disk |
| Decoded outputs in `~/.cache/fig-decode/` (via `--out=`) | ✅ | ✅ |

On every session start, Claude Code scans `~/.claude/skills/` and loads each `SKILL.md`. The fig-decode skill is in context automatically. The `find_node.py` helper picks the most recently modified `fig-decode-*` directory in `$TMPDIR` — so if you decoded yesterday and the files are still there, today's session reuses them with no re-decode.

For persistent storage across reboots, pass `--out=` to a durable location:

```bash
~/.claude/skills/fig-decode/decode.sh \
    ~/Downloads/MyDesign.fig \
    --out=~/.cache/fig-decode/MyDesign
```

## Limits

- **Structural tree only by default.** `nodes-summary.json` captures `type`, `name`, `parent`, `guid`, `phase`. Pixel-level properties (fills, strokes, fonts, geometry) exist in `document.bin` but the lightweight walker doesn't surface them. Pass `--full` to dump the entire decoded `Message[]`.
- **Outputs go to `$TMPDIR`.** Cleared on macOS reboot. Pass `--out=DIR` to persist.
- **The `.fig` / `.jam` file is huge.** Don't commit it to git. Re-download from Figma when the design changes significantly.
- **v100+ assumed.** Older `.fig` files (v15-v99) use a different layout. Not supported by this decoder; use `fig-kiwi@0.0.1` for those instead.
- **FigJam connector graph isn't a parent/child tree.** Walking `nodes-summary.json` alone won't reconstruct a flow — you need `--full` and to follow connector endpoints. See _Non-obvious gotcha #5_ above.

## When NOT to use this

- The design is on Figma cloud and you have an API token → use the [Figma REST API](https://www.figma.com/developers/api). Faster for single-screen lookups.
- You only need a single screen's image → just take a Figma screenshot.
- You're trying to render the actual pixels of a node → this decoder gives you structure, not pixels.

## Tooling provenance

- **[kiwi-schema](https://github.com/evanw/kiwi)** (0.5.0) — Evan Wallace's binary serialization library, MIT-licensed.
- **[pako](https://github.com/nodeca/pako)** (^2.1) — Pure-JS zlib port (DEFLATE/INFLATE), MIT-licensed.
- **[zstd](https://github.com/facebook/zstd)** — Facebook's zstandard compression CLI, BSD-licensed.

This is not reverse-engineering Figma's product — it's reading files **you** authored and exported. The `.fig` format is undocumented but reading your own designs is fair use.

## Maintenance

If a future Figma update changes the format and this decoder breaks:

1. Check the first 4 bytes of each chunk — Figma may switch compression again.
2. Compare the new schema (`schema.txt`) against an old one to spot new types.
3. If `compileSchema` chokes on a new primitive type, upgrade `kiwi-schema` (0.5 added uint64 support that 0.4 lacked).
4. If FigJam ships a new sub-version magic (e.g. `fig-jam:`), widen the `MAGIC_RE` regex in `decode.js`.

## Contributing

PRs welcome. Particularly valuable:

- Extend the walker to surface fills / strokes / fonts / positions in `nodes-summary.json` (the data is there in `document.bin`, just needs more fields captured).
- Support older `.fig` formats (v15-v99) — falls back to `fig-kiwi@0.0.1` semantics.
- A Python equivalent of `decode.js` so the whole pipeline runs without Node.

## License

[MIT](./LICENSE)

## Format reference

- [Kiwi binary schema spec](https://github.com/evanw/kiwi/blob/master/binary.md)
