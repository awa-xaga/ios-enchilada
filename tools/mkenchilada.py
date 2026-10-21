#!/usr/bin/env python3
"""Pack the shim into an OnePlus 6 (enchilada) boot.img.

The 4.19 Android kernel is only used as the container that this phone's ABL
already accepts: its Image.gz-dtb provides the DTB table (three FDTs appended
after the gzip stream), and its boot header gives the load addresses. The
shim replaces the compressed kernel and the XNU payload replaces the ramdisk.

  mkenchilada.py --kernel-gz-dtb Image.gz-dtb --payload payload.bin \
      --shim shim/out/Image --out shim-boot-enchilada.img

Without --payload an empty cpio ramdisk is used, which still reaches the
shim's UFS/DTB diagnostics. --template takes the addresses, cmdline and OS
version from an existing boot.img instead of the SDM845 defaults.
"""
import argparse
import gzip
import io
import os
import struct
import sys
import zlib

FDT_MAGIC = b"\xd0\x0d\xfe\xed"
PAGE = 4096
HEADER_V1_SIZE = 1648


def die(msg):
    sys.exit("mkenchilada: " + msg)


def parse_boot_img(path):
    b = open(path, "rb").read()
    if b[:8] != b"ANDROID!":
        die(f"{path}: not an Android boot image")
    (ks, ka, rs, ra, ss, sa, ta, ps, ver, osv) = struct.unpack_from("<10I", b, 8)
    if ver not in (0, 1, 2):
        die(f"{path}: unsupported header version {ver}")
    info = dict(kernel_addr=ka, ramdisk_addr=ra, second_addr=sa, tags_addr=ta,
                page_size=ps, header_version=ver, os_version=osv,
                cmdline=b[64:64 + 512].split(b"\0")[0].decode("latin-1"))
    if ver == 1:
        info["header_size"] = struct.unpack_from("<I", b, 1644)[0]
    return info


def gz_no_timestamp(data):
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", compresslevel=9, mtime=0) as g:
        g.write(data)
    return out.getvalue()


def split_image_gz_dtb(data):
    """Return (gzip stream, appended DTB table) using the gzip end marker."""
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    d.decompress(data)
    if not d.eof:
        die("Image.gz-dtb: truncated gzip stream")
    tail = d.unused_data
    if not tail.startswith(FDT_MAGIC):
        die("Image.gz-dtb: no appended device tree after the gzip stream")
    return data[:len(data) - len(tail)], tail


def empty_ramdisk():
    """A minimal newc cpio, like shim/build.sh creates without a payload."""
    def entry(name, ino, mode):
        name_b = name.encode() + b"\0"
        hdr = (f"070701{ino:08x}{mode:08x}{0:08x}{0:08x}{1:08x}{0:08x}"
               f"{0:08x}{0:08x}{0:08x}{0:08x}{0:08x}{len(name_b):08x}{0:08x}").encode()
        assert len(hdr) == 110
        out = hdr + name_b
        return out + b"\0" * ((-len(out)) % 4)
    data = entry(".", 1, 0o040755) + entry("TRAILER!!!", 0, 0)
    return gz_no_timestamp(data)


def encode_os_version(version, patch):
    try:
        major, minor, patch_level = (int(x) for x in version.split("."))
        year, month = (int(x) for x in patch.split("-"))
    except ValueError:
        die("--os-version must be A.B.C and --os-patch-level YYYY-MM")
    if not 0 <= major < 128 or not 0 <= minor < 128 or not 0 <= patch_level < 128:
        die("--os-version component out of range")
    return ((major << 25) | (minor << 18) | (patch_level << 11) |
            ((year - 2000) << 4) | (month & 0xf))


def write_boot_img(out, kernel, ramdisk, info, cmdline):
    ps = info["page_size"]
    pad = lambda b: b + b"\0" * ((-len(b)) % ps)
    kernel_p = pad(kernel)
    ramdisk_p = pad(ramdisk)
    second_p = b""

    hdr = bytearray(ps)
    hdr[0:8] = b"ANDROID!"
    struct.pack_into("<10I", hdr, 8,
                     len(kernel), info["kernel_addr"],
                     len(ramdisk), info["ramdisk_addr"],
                     0, info["second_addr"],
                     info["tags_addr"], ps, 1, info["os_version"])
    cmd = cmdline.encode()
    if len(cmd) >= 512:
        die("cmdline too long")
    hdr[64:64 + len(cmd)] = cmd
    # v1 extra header: no recovery_dtbo, header_size = 1648
    struct.pack_into("<I", hdr, 1632, 0)
    struct.pack_into("<Q", hdr, 1636, 0)
    struct.pack_into("<I", hdr, 1644, HEADER_V1_SIZE)

    with open(out, "wb") as f:
        f.write(hdr)
        f.write(kernel_p)
        f.write(ramdisk_p)
        f.write(second_p)

    total = ps + len(kernel_p) + len(ramdisk_p)
    sha = __import__("hashlib").sha256(open(out, "rb").read()).hexdigest()
    return dict(kernel_size=len(kernel), ramdisk_size=len(ramdisk),
                data_size=total, sha256=sha)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kernel-gz-dtb", required=True,
                    help="AOSP Image.gz-dtb (kernel gzip + appended DTBs)")
    ap.add_argument("--shim", default=os.path.join(os.path.dirname(__file__), "../shim/out/Image"),
                    help="shim raw Image (default: shim/out/Image)")
    ap.add_argument("--payload", help="XNU payload from tools/mkpayload.py")
    ap.add_argument("--out", required=True, help="output boot.img")
    ap.add_argument("--template", help="existing boot.img to copy header fields from")
    ap.add_argument("--cmdline", help="boot.img cmdline (default: template's, else console=null)")
    ap.add_argument("--os-version", default="17.0.0")
    ap.add_argument("--os-patch-level", default="2026-08")
    args = ap.parse_args()

    if args.template:
        info = parse_boot_img(args.template)
        if info["header_version"] != 1:
            die("this port expects a header v1 template")
        cmdline = args.cmdline if args.cmdline is not None else info["cmdline"]
    else:
        info = dict(kernel_addr=0x8000, ramdisk_addr=0x1000000, second_addr=0x0,
                    tags_addr=0x100, page_size=PAGE, header_version=1,
                    os_version=encode_os_version(args.os_version, args.os_patch_level))
        cmdline = args.cmdline if args.cmdline is not None else "console=null"

    ref = open(args.kernel_gz_dtb, "rb").read()
    _, dtbs = split_image_gz_dtb(ref)
    shim = open(args.shim, "rb").read()
    if shim[:2] == b"\x1f\x8b":
        die(f"{args.shim} is already gzip; pass the raw shim Image")
    kernel = gz_no_timestamp(shim) + dtbs
    ramdisk = open(args.payload, "rb").read() if args.payload else empty_ramdisk()
    if args.payload and len(ramdisk) < 16:
        die("payload is suspiciously small")

    res = write_boot_img(args.out, kernel, ramdisk, info, cmdline)
    print(f"shim      {len(shim)} bytes -> gzip {len(kernel) - len(dtbs)}")
    print(f"dtb table {len(dtbs)} bytes (first FDT at end of gzip), {dtbs.count(FDT_MAGIC)} FDTs")
    print(f"ramdisk   {res['ramdisk_size']} bytes"
          f"{' (payload)' if args.payload else ' (empty cpio)'}")
    print(f"out       {args.out}: {res['data_size']} bytes, sha256 {res['sha256']}")
    print(f"header    v1 kernel=0x{info['kernel_addr']:x} ramdisk=0x{info['ramdisk_addr']:x} "
          f"tags=0x{info['tags_addr']:x} page={info['page_size']}")


if __name__ == "__main__":
    main()
