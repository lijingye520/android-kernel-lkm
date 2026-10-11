#!/usr/bin/env python3
"""Extract ABI baseline sections from a vendor .ko (no external tools needed).

Exports the things Phase 2 of the android-kernel-lkm skill needs:
  - vermagic        (.modinfo)
  - build id        (.note.gnu.build-id)
  - __versions      (64-byte entries: CRC in the first 4 bytes, symbol name at offset 8)
  - __version_ext   (__version_ext_crcs + __version_ext_names, paired by order)

Usage:
  python3 extract-abi.py vendor.ko
  python3 extract-abi.py vendor.ko --module-symvers crc/Module.symvers
  python3 extract-abi.py vendor.ko --json abi/baseline.json

The 64-byte __versions stride and the name offset are the part hand-parsing gets
wrong: the CRC is at offset 0 and the symbol name starts at offset 8, so a naive
"u32 crc + char name" read desynchronises immediately.
"""

import argparse
import json
import struct
import sys

VERSIONS_STRIDE = 64
VER_NAME_OFFSET = 8

SHT_PROGBITS = 1
SHT_NOTE = 7


class ElfError(Exception):
    pass


def read_sections(path):
    """Return {name: bytes} for every PROGBITS section in an ELF64 little-endian file."""
    with open(path, "rb") as fh:
        data = fh.read()

    if data[:4] != b"\x7fELF":
        raise ElfError("not an ELF file: %s" % path)
    if data[4] != 2 or data[5] != 1:
        raise ElfError("only 64-bit little-endian ELF is supported")

    (e_shoff,) = struct.unpack_from("<Q", data, 0x28)
    (e_shentsize,) = struct.unpack_from("<H", data, 0x3A)
    (e_shnum,) = struct.unpack_from("<H", data, 0x3C)
    (e_shstrndx,) = struct.unpack_from("<H", data, 0x3E)

    if e_shoff == 0 or e_shnum == 0:
        raise ElfError("no section headers")

    def section_header(index):
        off = e_shoff + index * e_shentsize
        if off + e_shentsize > len(data):
            raise ElfError("section header %d out of range" % index)
        return struct.unpack_from("<IIQQQQIIQQ", data, off)

    _, _, _, _, _, _, _, _, shstr_off, _ = section_header(e_shstrndx)
    # shstrtab: sh_offset at index 4 of the unpacked tuple below
    shstr = section_header(e_shstrndx)
    strtab = data[shstr[4]:shstr[4] + shstr[5]]

    def cstr(buf, start):
        end = buf.find(b"\x00", start)
        if end < 0:
            end = len(buf)
        return buf[start:end].decode("utf-8", "replace")

    sections = {}
    for i in range(e_shnum):
        sh = section_header(i)
        name_off, sh_type, _, _, sh_offset, sh_size = sh[0], sh[1], sh[2], sh[3], sh[4], sh[5]
        if name_off >= len(strtab):
            continue
        name = cstr(strtab, name_off)
        if sh_type in (SHT_PROGBITS, SHT_NOTE) and sh_size:
            sections[name] = data[sh_offset:sh_offset + sh_size]
    return sections


def parse_vermagic(sections):
    modinfo = sections.get(".modinfo")
    if not modinfo:
        return None
    for entry in modinfo.split(b"\x00"):
        if entry.startswith(b"vermagic="):
            return entry[len(b"vermagic="):].decode("utf-8", "replace")
    return None


def parse_build_id(sections):
    note = sections.get(".note.gnu.build-id")
    if not note:
        return None
    off = 0
    while off + 12 <= len(note):
        namesz, descsz, ntype = struct.unpack_from("<III", note, off)
        off += 12
        name = note[off:off + namesz].rstrip(b"\x00")
        off += (namesz + 3) & ~3
        desc = note[off:off + descsz]
        off += (descsz + 3) & ~3
        if ntype == 3 and name == b"GNU":
            return desc.hex()
    return None


def parse_versions(sections):
    blob = sections.get("__versions")
    if blob is None:
        return []
    if len(blob) % VERSIONS_STRIDE:
        print(
            "warning: __versions size %d is not a multiple of %d"
            % (len(blob), VERSIONS_STRIDE),
            file=sys.stderr,
        )
    entries = []
    for off in range(0, len(blob) - VERSIONS_STRIDE + 1, VERSIONS_STRIDE):
        (crc,) = struct.unpack_from("<I", blob, off)
        raw = blob[off + VER_NAME_OFFSET:off + VERSIONS_STRIDE]
        name = raw.split(b"\x00", 1)[0].decode("utf-8", "replace")
        if not name:
            continue
        entries.append((crc, name))
    return entries


def parse_version_ext(sections):
    crcs_blob = sections.get("__version_ext_crcs")
    names_blob = sections.get("__version_ext_names")
    if crcs_blob is None or names_blob is None:
        return []
    crcs = [
        struct.unpack_from("<I", crcs_blob, off)[0]
        for off in range(0, len(crcs_blob) - 3, 4)
    ]
    names = [
        part.decode("utf-8", "replace")
        for part in names_blob.split(b"\x00")
        if part
    ]
    if len(crcs) != len(names):
        print(
            "warning: __version_ext_crcs has %d entries but __version_ext_names has %d"
            % (len(crcs), len(names)),
            file=sys.stderr,
        )
    return list(zip(crcs, names))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ko", help="vendor .ko to read")
    ap.add_argument("--module-symvers", metavar="PATH",
                    help="write '<crc> <symbol>' lines from __versions (Module.symvers format)")
    ap.add_argument("--json", metavar="PATH", help="write the whole baseline as JSON")
    args = ap.parse_args()

    try:
        sections = read_sections(args.ko)
    except (ElfError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    vermagic = parse_vermagic(sections)
    build_id = parse_build_id(sections)
    versions = parse_versions(sections)
    version_ext = parse_version_ext(sections)

    print("# ABI baseline: %s" % args.ko)
    print("vermagic=%s" % (vermagic or "<missing>"))
    print("build-id=%s" % (build_id or "<missing>"))
    print("__versions entries=%d" % len(versions))
    for crc, name in versions:
        print("  %08x  %s" % (crc, name))
    print("__version_ext entries=%d" % len(version_ext))
    for crc, name in version_ext:
        print("  %08x  %s" % (crc, name))

    if not versions:
        print(
            "note: this module has no __versions section — the build may be "
            "CONFIG_MODVERSIONS=n, or the baseline must come from a different "
            "loaded module",
            file=sys.stderr,
        )

    if args.module_symvers:
        with open(args.module_symvers, "w") as fh:
            fh.write("# extracted from %s\n" % args.ko)
            for crc, name in versions:
                fh.write("0x%08x\t%s\n" % (crc, name))
        print("wrote %s" % args.module_symvers)

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(
                {
                    "source": args.ko,
                    "vermagic": vermagic,
                    "build_id": build_id,
                    "versions": [{"crc": c, "symbol": n} for c, n in versions],
                    "version_ext": [{"crc": c, "symbol": n} for c, n in version_ext],
                },
                fh,
                indent=2,
            )
        print("wrote %s" % args.json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
