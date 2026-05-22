#!/usr/bin/env python3
"""Look up a Figma node by its node-id (sessionID:localID or sessionID-localID).

Usage:
  ./scripts/find_node.py NODE_ID [--out=DIR]

Examples:
  ./scripts/find_node.py 52502:42168
  ./scripts/find_node.py 52502-42168 --out=/tmp/fig-decode-myfile

The script reads `nodes-summary.json` from the decoded output directory and
prints the matched node along with its parent chain and direct children. Useful
for mapping a Figma URL (which encodes the node-id) to a screen in the design
file.
"""
from __future__ import annotations
import argparse, json, os, sys


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("node_id", help="sessionID:localID or sessionID-localID")
    p.add_argument("--out", default=None, help="decoded output dir (default: $TMPDIR/fig-decode-*)")
    p.add_argument("--children-depth", type=int, default=1, help="how many child levels to print (default 1)")
    args = p.parse_args()

    nid = args.node_id.replace("-", ":")
    try:
        sid_s, lid_s = nid.split(":")
        sid, lid = int(sid_s), int(lid_s)
    except ValueError:
        print(f"Invalid node-id: {args.node_id!r} (expected NNNN:NNNN or NNNN-NNNN)", file=sys.stderr)
        return 2

    out_dir = args.out
    if not out_dir:
        import tempfile, glob
        candidates = sorted(glob.glob(os.path.join(tempfile.gettempdir(), "fig-decode-*")), key=os.path.getmtime, reverse=True)
        if not candidates:
            print("No --out provided and no fig-decode-* found in $TMPDIR. Run decode.sh first.", file=sys.stderr)
            return 2
        out_dir = candidates[0]
        print(f"# using --out={out_dir}", file=sys.stderr)

    summary_path = os.path.join(out_dir, "nodes-summary.json")
    if not os.path.exists(summary_path):
        print(f"nodes-summary.json missing at {summary_path}", file=sys.stderr)
        return 2

    with open(summary_path) as f:
        nodes = json.load(f)

    by_guid = {}
    for n in nodes:
        g = n.get("guid")
        if g and g.get("localID") is not None:
            by_guid[(g["sessionID"], g["localID"])] = n

    hit = by_guid.get((sid, lid))
    if not hit:
        print(f"Not found: {sid}:{lid}", file=sys.stderr)
        return 1

    print(f"FOUND {sid}:{lid} → [{hit.get('type')}] {hit.get('name')!r}")
    print("\nParent chain (innermost → root):")
    cur = hit
    for _ in range(20):
        print(f"  [{cur.get('type','?'):10}] {cur.get('name')!r}")
        p = cur.get("parent")
        if not p:
            break
        cur = by_guid.get((p.get("sessionID"), p.get("localID")))
        if not cur:
            break

    def kids_of(node, depth=1):
        if depth <= 0:
            return
        nk = (node["guid"]["sessionID"], node["guid"]["localID"])
        kids = [n for n in nodes if n.get("parent") and (n["parent"].get("sessionID"), n["parent"].get("localID")) == nk]
        for k in kids:
            indent = "  " * (args.children_depth - depth + 1)
            print(f"{indent}[{k.get('type','?'):8}] {k.get('name')!r}")
            kids_of(k, depth - 1)

    print(f"\nChildren (depth {args.children_depth}):")
    kids_of(hit, args.children_depth)
    return 0


if __name__ == "__main__":
    sys.exit(main())
