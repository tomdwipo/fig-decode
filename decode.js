#!/usr/bin/env node
// Decode a Figma .fig file (format v100+) into a JSON node tree.
//
// Usage:
//   node decode.js <path/to/file.fig> [--out=DIR] [--full]
//
// Outputs in --out (default $TMPDIR/fig-decode-<basename>):
//   canvas.fig, meta.json, thumbnail.png, images/, schema.bin, schema.txt,
//   document.bin, nodes-summary.json, stats.json, message-full.json (--full only)

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');
const pako = require('pako');
const { decodeBinarySchema, compileSchema, prettyPrintSchema, ByteBuffer } = require('kiwi-schema');

const args = process.argv.slice(2);
if (args.length === 0 || args.includes('-h') || args.includes('--help')) {
    console.error('Usage: node decode.js <file.fig> [--out=DIR] [--full]');
    process.exit(args.length === 0 ? 2 : 0);
}
const figPath = args.find(a => !a.startsWith('-'));
if (!figPath || !fs.existsSync(figPath)) {
    console.error(`Input .fig not found: ${figPath}`);
    process.exit(2);
}
const outArg = args.find(a => a.startsWith('--out='));
const FULL = args.includes('--full');
const base = path.basename(figPath, '.fig').replace(/\s+/g, '_');
const OUT = outArg ? outArg.slice(6) : path.join(os.tmpdir(), `fig-decode-${base}`);
fs.mkdirSync(OUT, { recursive: true });
function log(msg) { console.error(`[fig-decode] ${msg}`); }

log(`unzip → ${OUT}`);
execFileSync('unzip', ['-o', '-q', figPath, '-d', OUT]);
const canvasPath = path.join(OUT, 'canvas.fig');
if (!fs.existsSync(canvasPath)) throw new Error('canvas.fig missing inside outer ZIP');

const canvas = fs.readFileSync(canvasPath);
const PRELUDE = 'fig-kiwi';
if (canvas.slice(0, 8).toString() !== PRELUDE) throw new Error('Bad magic');
const dv = new DataView(canvas.buffer, canvas.byteOffset, canvas.byteLength);
const version = dv.getUint32(8, true);
log(`fig-kiwi version ${version}`);

let off = 12;
const chunks = [];
while (off + 4 <= canvas.length) {
    const size = dv.getUint32(off, true);
    off += 4;
    if (off + size > canvas.length) break;
    chunks.push(canvas.subarray(off, off + size));
    off += size;
}
log(`chunks: ${chunks.length} (sizes: ${chunks.map(c => c.length).join(', ')})`);

function isZstd(buf) {
    return buf[0] === 0x28 && buf[1] === 0xb5 && buf[2] === 0x2f && buf[3] === 0xfd;
}
function zstdDecompressFile(buf, scratchPath) {
    fs.writeFileSync(scratchPath, Buffer.from(buf));
    const outPath = scratchPath.replace(/\.zst$/, '.tmp');
    execFileSync('zstd', ['-d', '--force', '-q', scratchPath, '-o', outPath]);
    const out = fs.readFileSync(outPath);
    fs.unlinkSync(scratchPath);
    fs.unlinkSync(outPath);
    return out;
}

let schemaBytes;
if (isZstd(chunks[0])) {
    log('chunk[0] zstd');
    schemaBytes = zstdDecompressFile(chunks[0], path.join(OUT, 'schema.zst'));
} else {
    log('chunk[0] DEFLATE');
    schemaBytes = pako.inflateRaw(chunks[0]);
}
fs.writeFileSync(path.join(OUT, 'schema.bin'), Buffer.from(schemaBytes));
const schema = decodeBinarySchema(schemaBytes);
fs.writeFileSync(path.join(OUT, 'schema.txt'), prettyPrintSchema(schema));
log(`schema: ${schema.definitions.length} definitions`);

let docBytes;
if (isZstd(chunks[1])) {
    log('chunk[1] zstd');
    docBytes = zstdDecompressFile(chunks[1], path.join(OUT, 'document.zst'));
} else {
    log('chunk[1] DEFLATE');
    docBytes = pako.inflateRaw(chunks[1]);
}
fs.writeFileSync(path.join(OUT, 'document.bin'), Buffer.from(docBytes));
log(`document: ${docBytes.length.toLocaleString()} bytes`);

const compiled = compileSchema(schema);
const bb = new ByteBuffer(Buffer.from(docBytes));
const messages = [];
const t0 = Date.now();
try {
    while (bb._index < docBytes.length) messages.push(compiled.decodeMessage(bb));
} catch (e) {
    log(`stream stop at ${bb._index}/${docBytes.length}: ${e.message}`);
}
log(`messages: ${messages.length} in ${((Date.now() - t0) / 1000).toFixed(1)}s`);

const nodes = [];
const types = {};
const pages = [];
for (const m of messages) {
    if (!m.nodeChanges) continue;
    for (const nc of m.nodeChanges) {
        nodes.push({
            guid: nc.guid,
            parent: nc.parentIndex && nc.parentIndex.guid,
            phase: nc.phase,
            type: nc.type,
            name: nc.name,
        });
        types[nc.type || '?'] = (types[nc.type || '?'] || 0) + 1;
        if (nc.type === 'CANVAS') pages.push(nc.name);
    }
}
fs.writeFileSync(path.join(OUT, 'nodes-summary.json'), JSON.stringify(nodes));
fs.writeFileSync(path.join(OUT, 'stats.json'), JSON.stringify({
    figmaFormatVersion: version,
    messageCount: messages.length,
    nodeCount: nodes.length,
    typeCounts: types,
    pageNames: [...new Set(pages)],
    decodedAt: new Date().toISOString(),
}, null, 2));
log(`nodes: ${nodes.length.toLocaleString()}`);
log(`pages: ${new Set(pages).size}`);

if (FULL) {
    log('writing message-full.json (large)');
    fs.writeFileSync(path.join(OUT, 'message-full.json'), JSON.stringify(messages));
}

console.log(OUT);
