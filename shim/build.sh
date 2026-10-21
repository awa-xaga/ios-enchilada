#!/bin/bash
# Build the shim. BOARD=sweet (default) also wraps it in the PixelOS-style
# boot.img v2; BOARD=enchilada stops at out/Image because that port reuses the
# Android boot.img container (see tools/mkenchilada.py).
set -euo pipefail
cd "$(dirname "$0")"
BOARD=${BOARD:-sweet}
case "$BOARD" in
	sweet)		BOARD_DEF=-DBOARD_SWEET ;;
	enchilada)	BOARD_DEF=-DBOARD_ENCHILADA ;;
	*) echo "unknown BOARD=$BOARD (sweet|enchilada)" >&2; exit 1 ;;
esac
CC=aarch64-linux-gnu-gcc
OBJCOPY=aarch64-linux-gnu-objcopy
CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra $BOARD_DEF"
mkdir -p out
for f in start.S shim.c console.c mmu.c fdt.c loader.c ufs.c; do
	$CC $CFLAGS -c $f -o out/${f%.*}.o
done
# The image runs wherever ABL puts it with no relocation pass: only the
# header's image_size (start.o, linked at 0) may be an absolute address.
abs=$(aarch64-linux-gnu-readelf -r out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocations in C objects" >&2; exit 1; }
$CC $CFLAGS -static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N \
	out/start.o out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o -o out/shim.elf
$OBJCOPY -O binary out/shim.elf out/Image
# ABL copies the file; pad to image_size so .bss/stacks exist as zeroed bytes.
size_hex=$(aarch64-linux-gnu-nm out/shim.elf | awk '$3=="_end"{print $1}')
size=$((16#$size_hex))
truncate -s "$size" out/Image
# Host render of the console layout (uses the same FB_W/FB_H/FB_STRIDE).
gcc -O1 -Wall $BOARD_DEF -o out/host_test console.c host_test.c && ./out/host_test
if [ "$BOARD" = enchilada ]; then
	echo "board=enchilada: out/Image ready"
	echo "pack with: python3 ../tools/mkenchilada.py --kernel-gz-dtb PATH --out out/shim-boot-enchilada.img"
	exit 0
fi
# Ramdisk: an xnu payload (tools/mkpayload.py) if given as $1, else an empty
# newc cpio (ABL dislikes a zero-size ramdisk on some builds) -> diagnostics.
if [ -n "${1:-}" ]; then
	cp "$1" out/ramdisk.bin
else
	(cd out && rm -rf rd && mkdir rd && cd rd && find . | cpio -o -H newc --quiet | gzip -9 > ../ramdisk.bin)
fi
if command -v mkbootimg >/dev/null 2>&1; then
	mkbootimg --header_version 2 --kernel out/Image --ramdisk out/ramdisk.bin \
		--dtb ../dtb/boot_unpacked/dtb --base 0 --kernel_offset 0x8000 --ramdisk_offset 0x1000000 \
		--tags_offset 0x100 --dtb_offset 0x1f00000 --pagesize 4096 \
		--os_version 17.0.0 --os_patch_level 2035-06 \
		--cmdline "console=null" -o out/shim-boot.img
	ls -l out/Image out/shim-boot.img
else
	echo "mkbootimg not found: out/Image and out/ramdisk.bin are ready" >&2
fi
