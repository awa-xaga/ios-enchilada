/*
 * Per-board fixed addresses. Pick one at compile time with BOARD=<name> in
 * build.sh (-DBOARD_SWEET / -DBOARD_ENCHILADA). Anything that differs between
 * ports and cannot be read from the live FDT belongs here.
 */
#pragma once

#if defined(BOARD_ENCHILADA)
/* OnePlus 6 (SDM845): reserved-memory/cont_splash_region@9d400000, 1080x2280 */
#define BOARD_NAME	"enchilada"
#define FB_PHYS		0x9d400000UL
#define FB_W		1080
#define FB_H		2280
#elif defined(BOARD_SWEET)
/* Redmi Note 10 Pro (SM7150): reserved-memory/cont_splash_region@9c000000 */
#define BOARD_NAME	"sweet"
#define FB_PHYS		0x9c000000UL
#define FB_W		1080
#define FB_H		2400
#else
#error "select a board: -DBOARD_SWEET or -DBOARD_ENCHILADA"
#endif

#define FB_BASE		FB_PHYS
#define FB_STRIDE	(FB_W * 4)	/* a8r8g8b8, matches mainline simplefb */
