#!/bin/bash
# Build the OnePlus 6 (enchilada) iOS boot image from the stock boot.img.
#
#   tools/mkiosboot.sh STOCK_BOOT.IMG XNU_KERNEL [OUT.img]
#
# Inputs:
#   STOCK_BOOT.IMG  the phone's stock boot.img (OOS). Only its Image.gz-dtb
#                   (the appended DTB table) and its header are reused.
#   XNU_KERNEL      kernel.development.sweet from the CI artifact (xnu/out-*).
#   OUT.img         default shim/out/shim-boot-enchilada.img
#
# Needs research/ipsw-x/d22ap.adt (the iPhone X device tree, extracted once):
#   tools/remotezip.py <IPSW URL> DeviceTree.d22ap.im4p research/ipsw-x
#   tools/im4p-extract.py research/ipsw-x/Firmware/all_flash/DeviceTree.d22ap.im4p \
#       research/ipsw-x/d22ap.adt
# without it the ADT has no /product node and iOS reports the wrong device.
set -euo pipefail
cd "$(dirname "$0")/.."

BOOT=${1:?usage: mkiosboot.sh STOCK_BOOT.IMG XNU_KERNEL [OUT.img]}
KERNEL=${2:?usage: mkiosboot.sh STOCK_BOOT.IMG XNU_KERNEL [OUT.img]}
OUT=${3:-shim/out/shim-boot-enchilada.img}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# The boot-args the known-good enchilada image used: one CPU, watchdog pet,
# no kernel console over the GUI, 30 Hz present, HFS+ root on UFS.
CMDLINE='debug=0xc cpus=1 keepsyms=1 -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=30 startup_debug=1'

echo "== shim (BOARD=enchilada)"
BOARD=enchilada ./shim/build.sh

echo "== device tree (D22AP /product, high bank, /pram 0x100000000)"
python3 tools/mkadt.py shim/out/ench-adt.adt --board enchilada --highmem

echo "== payload (xnu + ADT + boot-args)"
python3 tools/mkpayload.py "$KERNEL" shim/out/ench-adt.adt shim/out/payload-ench.bin \
	--cmdline "$CMDLINE"

echo "== Image.gz-dtb out of $BOOT"
python3 - "$BOOT" "$TMP/Image.gz-dtb" <<'PY'
import struct, sys
b = open(sys.argv[1], 'rb').read()
if b[:8] != b'ANDROID!':
    sys.exit(f'{sys.argv[1]}: not an Android boot image')
ks, = struct.unpack_from('<I', b, 8)
ps, = struct.unpack_from('<I', b, 36)
open(sys.argv[2], 'wb').write(b[ps:ps + ks])
PY

echo "== boot.img"
python3 tools/mkenchilada.py --kernel-gz-dtb "$TMP/Image.gz-dtb" \
	--shim shim/out/Image --payload shim/out/payload-ench.bin \
	--template "$BOOT" --out "$OUT"

echo "== done: $OUT"
echo "   boot it with: fastboot boot $OUT"
