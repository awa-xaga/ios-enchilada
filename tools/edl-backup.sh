#!/bin/bash
# Read-only EDL backup of an OnePlus 6 (enchilada) before flashing anything.
#
#   tools/edl-backup.sh LOADER [OUTDIR]
#
# LOADER is a signed firehose loader (e.g. Loaders/qualcomm/factory/
# sdm845_sdm850_sda845/*_fhprg.bin). The phone must be in EDL (9008):
# power off, hold Vol+ and Vol-, plug USB; `lsusb` shows 05c6:9008.
#
# Dumps the GPT and every partition except the ROM/userdata ones below into
# OUTDIR (default backup/enchilada-edl-<time>), then writes SHA256SUMS.
# Nothing is written to the phone (`rl` = read list).
set -euo pipefail

[[ $# -ge 1 ]] || { sed -n '2,13p' "$0"; exit 2; }
loader=$(realpath "$1")
root=$(cd "$(dirname "$0")/.." && pwd)
out=${2:-$root/backup/enchilada-edl-$(date +%Y%m%d-%H%M%S)}
edl=$root/edl/edl-master/edl.py
py=${PY:-$root/edl/venv/bin/python}

[[ -f $loader ]] || { echo "no such loader: $loader" >&2; exit 1; }
[[ -f $edl ]] || { echo "missing $edl (download bkerler/edl)" >&2; exit 1; }
[[ -x $py ]] || py=python3
lsusb | grep -q '05c6:9008' || { echo "phone is not in EDL (no 05c6:9008)" >&2; exit 1; }

# Huge and/or reinstallable: super/userdata, the A/B system images and logs.
# boot/dtbo/vbmeta, the bootloader chain, modem/calibration and persist stay.
skip='userdata,super,system_a,system_b,vendor_a,vendor_b,product_a,product_b,odm_a,odm_b,op1,op2,cache,metadata,logfs,logdump,minidump,rawdump'
mkdir -p "$out"

echo "loader: $loader" | tee "$out/BACKUP.txt"
echo "out:    $out" | tee -a "$out/BACKUP.txt"
sha256sum "$loader" | tee -a "$out/BACKUP.txt"

"$py" "$edl" rl "$out" --loader="$loader" --memory=ufs --skip="$skip" --genxml \
	2>&1 | tee "$out/rl.log"

if [[ -f $out/gpt_main0.bin ]]; then
	"$py" "$root/tools/gpt-list.py" "$out/gpt_main0.bin" | tee "$out/partitions.txt"
fi

(cd "$out" && sha256sum *.bin > SHA256SUMS)
echo "done: $out" >&2
