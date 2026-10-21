/*
 * Just enough flattened-device-tree parsing to find what ABL put in
 * /chosen (initrd location). Big-endian, 4-byte aligned tokens.
 */
#include "fdt.h"

#define FDT_MAGIC	0xd00dfeed
#define FDT_BEGIN_NODE	1
#define FDT_END_NODE	2
#define FDT_PROP	3
#define FDT_NOP		4
#define FDT_END		9

static uint32_t be32(uintptr_t a)
{
	return __builtin_bswap32(*(volatile uint32_t *)a);
}

static int streq(const char *a, const char *b)
{
	while (*a && *a == *b)
		a++, b++;
	return *a == *b;
}

static uintptr_t align4(uintptr_t a)
{
	return (a + 3) & ~3UL;
}

static uintptr_t skip_str(uintptr_t p)
{
	/* byte loads are fine on Device memory as long as they are aligned to 1 */
	while (*(volatile char *)p)
		p++;
	return p + 1;
}

/* Node name is prefix, optionally followed by a unit address ("@..."). */
static int node_match(const char *s, const char *p)
{
	while (*p)
		if (*s++ != *p++)
			return 0;
	return *s == '\0' || *s == '@';
}

int fdt_node_prop(uintptr_t fdt, const char *prefix, const char *prop,
    const void **val, uint32_t *len)
{
	if (!fdt || be32(fdt) != FDT_MAGIC)
		return 0;
	uintptr_t p = fdt + be32(fdt + 8);		/* off_dt_struct */
	uintptr_t strings = fdt + be32(fdt + 12);	/* off_dt_strings */
	int depth = 0, target_depth = 0, in_target = 0;

	for (;;) {
		uint32_t tok = be32(p);
		p += 4;
		switch (tok) {
		case FDT_BEGIN_NODE: {
			const char *name = (const char *)p;
			depth++;
			if (!in_target && node_match(name, prefix)) {
				in_target = 1;
				target_depth = depth;
			}
			p = align4(skip_str(p));
			break;
		}
		case FDT_END_NODE:
			if (in_target && depth == target_depth)
				return 0;
			depth--;
			break;
		case FDT_PROP: {
			uint32_t l = be32(p), nameoff = be32(p + 4);
			uintptr_t v = p + 8;
			if (in_target && streq((const char *)(strings + nameoff), prop)) {
				*val = (const void *)v;
				*len = l;
				return 1;
			}
			p = align4(v + l);
			break;
		}
		case FDT_NOP:
			break;
		default:	/* FDT_END or garbage */
			return 0;
		}
	}
}

int fdt_node_reg64(uintptr_t fdt, const char *prefix, int idx,
    uint64_t *addr, uint64_t *size)
{
	const void *val;
	uint32_t len;
	if (!fdt_node_prop(fdt, prefix, "reg", &val, &len))
		return 0;
	/* Qualcomm base trees use #address-cells = #size-cells = 2 -> 16 bytes. */
	uint32_t ent = (len % 16 == 0) ? 16 : (len % 8 == 0 ? 8 : 0);
	if (!ent || idx < 0 || (uint32_t)idx >= len / ent)
		return 0;
	uintptr_t r = (uintptr_t)val + (uintptr_t)idx * ent;
	if (ent == 16) {
		*addr = (uint64_t)be32(r) << 32 | be32(r + 4);
		*size = (uint64_t)be32(r + 8) << 32 | be32(r + 12);
	} else {
		*addr = be32(r);
		*size = be32(r + 4);
	}
	return 1;
}

int fdt_chosen_u64(uintptr_t fdt, const char *prop, uint64_t *out)
{
	if (!fdt || be32(fdt) != FDT_MAGIC)
		return 0;
	uintptr_t p = fdt + be32(fdt + 8);		/* off_dt_struct */
	uintptr_t strings = fdt + be32(fdt + 12);	/* off_dt_strings */
	int depth = 0, in_chosen = 0;

	for (;;) {
		uint32_t tok = be32(p);
		p += 4;
		switch (tok) {
		case FDT_BEGIN_NODE: {
			const char *name = (const char *)p;
			depth++;
			in_chosen = depth == 2 && streq(name, "chosen");
			p = align4(skip_str(p));
			break;
		}
		case FDT_END_NODE:
			if (in_chosen)
				return 0;
			depth--;
			break;
		case FDT_PROP: {
			uint32_t len = be32(p), nameoff = be32(p + 4);
			uintptr_t val = p + 8;
			if (in_chosen && streq((const char *)(strings + nameoff), prop)) {
				if (len == 4)
					*out = be32(val);
				else if (len == 8)
					*out = (uint64_t)be32(val) << 32 | be32(val + 4);
				else
					return 0;
				return 1;
			}
			p = align4(val + len);
			break;
		}
		case FDT_NOP:
			break;
		default:	/* FDT_END or garbage */
			return 0;
		}
	}
}
