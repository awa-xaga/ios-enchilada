#!/usr/bin/env python3
"""Decode an Apple IM4P (Firmware/*.im4p) to its raw payload.

  im4p-extract.py DeviceTree.d22ap.im4p d22ap.adt

IM4P files are an ASN.1 SEQUENCE of OCTET STRINGs: magic "IM4P", a four-letter
type ("dtre"), a human-readable description ("EmbeddedDeviceTrees-<ver>") and
the payload itself. Apple stores the device trees LZFSE-compressed (the payload
starts with "bvx2"); the LZFSE decoder comes from the `lzfse` module
(pip install lzfse) or, if that is missing, from the `lzfse` command.
Uncompressed payloads (device trees of older SoCs) are copied as they are.
"""
import subprocess
import sys


def der_items(data):
    """Yield the content of every top-level DER item in data."""
    off = 0
    while off + 2 <= len(data):
        tag = data[off]
        off += 1
        if tag & 0x1f == 0x1f:                      # multi-byte tag number
            while off < len(data) and data[off] & 0x80:
                off += 1
            off += 1
        if off >= len(data):
            break
        n = data[off]
        off += 1
        if n & 0x80:                                # long form length
            k = n & 0x7f
            n = int.from_bytes(data[off:off + k], 'big')
            off += k
        yield tag, data[off:off + n]
        off += n


def lzfse_decompress(payload):
    try:
        import lzfse
    except ImportError:
        try:
            return subprocess.run(['lzfse', '-decode'], input=payload,
                                  check=True, capture_output=True).stdout
        except (OSError, subprocess.CalledProcessError):
            sys.exit('im4p-extract: LZFSE payload needs the `lzfse` module '
                     '(pip install lzfse) or the `lzfse` command')
    return lzfse.decompress(payload)


def main(argv):
    if len(argv) != 3:
        sys.exit('usage: im4p-extract.py IN.im4p OUT')
    data = open(argv[1], 'rb').read()
    parts = list(der_items(data))
    if parts and parts[0][0] == 0x30:              # SEQUENCE wrapping the body
        parts = list(der_items(parts[0][1]))
    if not parts or parts[0][1] != b'IM4P':
        sys.exit(f'{argv[1]}: no IM4P sequence')
    kind = parts[1][1] if len(parts) > 1 else b'?'
    # the payload is the largest OCTET STRING; a trailing SEQUENCE carries the
    # DER signature trailer (02 01 01 02 03 02 xx xx) and is not payload
    payloads = [c for t, c in parts if t == 0x04]
    if not payloads:
        sys.exit(f'{argv[1]}: no payload OCTET STRING')
    payload = max(payloads, key=len)
    if payload[:4] == b'bvx2' or payload[:4] == b'bvx-':
        out = lzfse_decompress(payload)
    else:
        out = payload
    open(argv[2], 'wb').write(out)
    print(f'{argv[1]}: {kind.decode("latin-1")} payload {len(payload)} bytes '
          f'-> {argv[2]} ({len(out)} bytes)')


if __name__ == '__main__':
    main(sys.argv)
