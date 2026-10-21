#pragma once
#include <stdint.h>

/* Read a u32/u64 (cell-size agnostic) property of /chosen. Returns 0 if absent. */
int fdt_chosen_u64(uintptr_t fdt, const char *prop, uint64_t *out);

/* First node whose name starts with prefix: its property value/length. */
int fdt_node_prop(uintptr_t fdt, const char *prefix, const char *prop,
    const void **val, uint32_t *len);

/* reg[idx] of the first node whose name starts with prefix. Handles the
 * Qualcomm 2/2 address/size cells (16 bytes per range) and 1/1 (8 bytes). */
int fdt_node_reg64(uintptr_t fdt, const char *prefix, int idx,
    uint64_t *addr, uint64_t *size);
