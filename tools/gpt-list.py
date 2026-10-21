#!/usr/bin/env python3
"""Print the partitions in an EDL gpt_mainN.bin (MBR + LBA1 header + entries).

  gpt-list.py gpt_main0.bin [SECTOR_SIZE]

The file that `edl.py rl`/`gpt` writes starts at LBA 0, so the entry array is
at entry_lba * sector_size. Prints name, first/last LBA and size in MiB.
"""
import struct
import sys


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    sector = int(sys.argv[2]) if len(sys.argv) > 2 else 4096
    b = open(path, "rb").read()
    off = sector
    if b[off:off + 8] != b"EFI PART":
        sys.exit(f"{path}: no GPT header at LBA 1")
    num = struct.unpack_from("<I", b, off + 80)[0]
    esz = struct.unpack_from("<I", b, off + 84)[0]
    ent_lba = struct.unpack_from("<Q", b, off + 72)[0]
    ent = ent_lba * sector
    print(f"# {path}: {num} entries x {esz} bytes at LBA {ent_lba}")
    print(f"{'name':24} {'first':>12} {'last':>12} {'MiB':>10}")
    for i in range(num):
        e = ent + i * esz
        if b[e:e + 16] == b"\0" * 16:
            continue
        first, last = struct.unpack_from("<QQ", b, e + 32)
        name = b[e + 56:e + 128].decode("utf-16le").split("\0")[0]
        size = (last - first + 1) * sector // (1024 * 1024)
        print(f"{name:24} {first:12d} {last:12d} {size:10d}")


if __name__ == "__main__":
    main()
