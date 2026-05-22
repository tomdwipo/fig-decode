"""Minimal Kiwi-schema reader (evanw/kiwi binary format).

Optional Python alternative to the Node `kiwi-schema` library — primarily for
ad-hoc inspection of the schema chunk and one-off scripting against the
decoded document. The Node decoder in `decode.js` is the recommended path; the
JS `kiwi-schema` compiler generates a fast typed walker, while this module is
a generic interpreter.

Schema layout (chunk[0] of fig-kiwi, after decompression):
  definitions     = varint count, then `count` definitions
  definition      = c-string name | u8 kind | varint field-count | field*
  field           = c-string name | svarint type | u8 isArray | varint value
    kind: 0=ENUM, 1=STRUCT, 2=MESSAGE
    type: -1 bool, -2 byte, -3 int(s32), -4 uint(u32), -5 float, -6 string,
          -7 int64, -8 uint64, >=0 index into definitions[]
    For ENUM members, `value` is the enum constant; for MESSAGE fields it is
    the field id (0 for STRUCT).

Document layout (chunk[1] decompressed against the schema):
  MESSAGE = [varint field_id, value]* then field_id=0
  STRUCT  = field values in declaration order, no IDs
  ENUM    = varint
  array<T> = varint count + T*
"""
from __future__ import annotations
import struct
from dataclasses import dataclass, field as dc_field
from typing import Any


class ByteReader:
    __slots__ = ("buf", "off")

    def __init__(self, buf: bytes, off: int = 0):
        self.buf = buf
        self.off = off

    def u8(self) -> int:
        b = self.buf[self.off]
        self.off += 1
        return b

    def u32(self) -> int:
        v = struct.unpack_from("<I", self.buf, self.off)[0]
        self.off += 4
        return v

    def f32(self) -> float:
        v = struct.unpack_from("<f", self.buf, self.off)[0]
        self.off += 4
        return v

    def varint(self) -> int:
        result = 0
        shift = 0
        while True:
            b = self.u8()
            result |= (b & 0x7f) << shift
            if (b & 0x80) == 0:
                return result
            shift += 7
            if shift >= 64:
                raise ValueError("varint too long")

    def svarint(self) -> int:
        v = self.varint()
        return (v >> 1) ^ -(v & 1)

    def cstring(self) -> str:
        start = self.off
        end = self.buf.find(b"\x00", start)
        if end < 0:
            raise ValueError("unterminated cstring")
        out = self.buf[start:end].decode("utf-8", "replace")
        self.off = end + 1
        return out


KIND_ENUM = 0
KIND_STRUCT = 1
KIND_MESSAGE = 2

PRIM_NAMES = {
    -1: "bool", -2: "byte", -3: "int", -4: "uint",
    -5: "float", -6: "string", -7: "int64", -8: "uint64",
}


@dataclass
class Field:
    name: str
    type: int       # signed; negative=prim, >=0 def index
    is_array: bool
    value: int      # enum value or message field id


@dataclass
class Definition:
    name: str
    kind: int       # 0/1/2
    fields: list = dc_field(default_factory=list)


def parse_schema(blob: bytes) -> list:
    r = ByteReader(blob)
    count = r.varint()
    defs = []
    for _ in range(count):
        name = r.cstring()
        kind = r.u8()
        fcount = r.varint()
        d = Definition(name=name, kind=kind)
        for _ in range(fcount):
            fname = r.cstring()
            ftype = r.svarint()
            is_array = r.u8() != 0
            fvalue = r.varint()
            d.fields.append(Field(fname, ftype, is_array, fvalue))
        defs.append(d)
    return defs


def type_name(t: int, defs: list) -> str:
    if t < 0:
        return PRIM_NAMES.get(t, f"prim({t})")
    if 0 <= t < len(defs):
        return defs[t].name
    return f"def#{t}"


def schema_to_text(defs: list) -> str:
    out = []
    for i, d in enumerate(defs):
        kind = ("enum", "struct", "message")[d.kind]
        out.append(f"// [{i}] {kind} {d.name} ({len(d.fields)} fields)")
        out.append(f"{kind} {d.name} {{")
        for f in d.fields:
            arr = "[]" if f.is_array else ""
            if d.kind == KIND_ENUM:
                out.append(f"  {f.name} = {f.value};")
            elif d.kind == KIND_MESSAGE:
                out.append(f"  {type_name(f.type, defs)}{arr} {f.name} = {f.value};")
            else:
                out.append(f"  {type_name(f.type, defs)}{arr} {f.name};")
        out.append("}\n")
    return "\n".join(out)
