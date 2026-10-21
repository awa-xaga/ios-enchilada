#!/bin/bash
# Read the SWEET persistent console log from the end of userdata over EDL.
#
#   tools/edl-read-log.sh [LOADER|-] [GPT_MAIN0] [OUT.bin]
#
# LOADER is a signed firehose loader for a fresh EDL (9008); use '-' when the
# firehose loader is already running. GPT_MAIN0 defaults to the backed-up
# enchilada GPT (tools/gpt-list.py can print any EDL gpt_mainN.bin).
# The log area is the last 1025 4 KiB blocks of the userdata partition:
# block 0 is the SWEETLOG header, the following 1024 blocks are the ring.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
loader=${1:--}
gpt=${2:-$root/backup/enchilada-edl-20261021/lun0/gpt_main0.bin}
out=${3:-/tmp/enchilada-sweetlog.bin}
edl=$root/edl/edl-master/edl.py
py=${PY:-$root/edl/venv/bin/python}

[[ -f $edl ]] || { echo "missing $edl (bkerler/edl)" >&2; exit 1; }
[[ -f $gpt ]] || { echo "missing GPT dump: $gpt" >&2; exit 1; }
[[ -x $py ]] || py=python3

loader_opt=()
if [[ $loader != - ]]; then
	loader=$(realpath "$loader")
	[[ -f $loader ]] || { echo "no such loader: $loader" >&2; exit 1; }
	loader_opt=(--loader="$loader")
fi

read -r first last < <("$py" - "$gpt" <<'PY'
import struct, sys
b = open(sys.argv[1], "rb").read()
sec = 4096
assert b[sec:sec+8] == b"EFI PART"
num = struct.unpack_from("<I", b, sec+80)[0]
esz = struct.unpack_from("<I", b, sec+84)[0]
ent = struct.unpack_from("<Q", b, sec+72)[0] * sec
for i in range(num):
    e = ent + i*esz
    if b[e:e+16] == b"\0"*16:
        continue
    name = b[e+56:e+128].decode("utf-16le").split("\0")[0]
    if name == "userdata":
        first, last = struct.unpack_from("<QQ", b, e+32)
        print(first, last)
        break
else:
    sys.exit("userdata not found in GPT")
PY
)
start=$((last - 1024))
echo "userdata LBA $first..$last; log area $start + 1025 blocks -> $out" >&2

"$py" "$edl" rs "$start" 1025 "$out" --sectorsize=4096 --memory=ufs "${loader_opt[@]}"
"$py" "$root/tools/sweet-log.py" "$out" "$out.txt"
echo "log: $out.txt" >&2
