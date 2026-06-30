/**
 * @file stk500v1.h
 * @brief STK500v1 protocol implementation for flashing ATmega328P via optiboot.
 *
 * Communicates with Arduino's optiboot bootloader over USB CDC using the
 * STK500v1 command set (verified against avrdude stk500.c + optiboot.c):
 *   - get_sync       (0x30 0x20)           -> 0x14 0x10
 *   - get_signature  (0x75 0x20)           -> 0x14 1E 95 0F 0x10
 *   - enter_progmode (0x50 0x20)           -> 0x14 0x10
 *   - load_address   (0x55 lo hi 0x20)     -> 0x14 0x10  (word address, LE)
 *   - prog_page      (0x64 len_hi len_lo 'F' data[] 0x20) -> 0x14 0x10
 *   - leave_progmode (0x51 0x20)           -> 0x14 (optiboot WDT-resets, OK optional)
 *
 * Every command is terminated with CRC_EOP=0x20. optiboot replies with
 * STK_INSYNC=0x14 immediately, then payload, then STK_OK=0x10.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

/* STK500v1 command bytes (from Atmel AVR061 command.h, matches optiboot) */
#define STK_CRC_EOP          0x20  /* End-of-packet sentinel */
#define STK_GET_SYNC         0x30  /* Echos sync, establishes comms */
#define STK_ENTER_PROGMODE   0x50  /* Enter programming mode */
#define STK_LEAVE_PROGMODE   0x51  /* Leave programming mode */
#define STK_LOAD_ADDRESS     0x55  /* Load address (word addr, LE) */
#define STK_PROG_PAGE        0x64  /* Program flash page */
#define STK_READ_PAGE        0x74  /* Read flash page (verify) */
#define STK_READ_SIGN        0x75  /* Read device signature bytes */

/* STK500v1 response bytes */
#define STK_INSYNC           0x14  /* Command accepted */
#define STK_OK               0x10  /* Command completed */
#define STK_NOSYNC           0x15  /* Lost sync */

/* ATmega328P device constants */
#define ATMEGA328P_SIG_0     0x1E
#define ATMEGA328P_SIG_1     0x95
#define ATMEGA328P_SIG_2     0x0F
#define ATMEGA328P_FLASH_SIZE   32768  /* bytes */
#define ATMEGA328P_PAGE_SIZE    128    /* bytes */

/* Timing / retries */
#define STK_SYNC_RETRIES        10    /* get_sync attempts (optiboot window ~1s) */
#define STK_CMD_TIMEOUT_MS      200   /* per-command response timeout */
#define STK_PAGE_TIMEOUT_MS     500   /* prog_page timeout (page write ~4ms) */
#define STK_LEAVE_TIMEOUT_MS    100   /* leave_progmode (OK may be absent) */

/**
 * @brief Initialise the STK500v1 layer (no USB work — just logging).
 * @return true always
 */
bool stk500v1_init(void);

/**
 * @brief Program a raw binary image into ATmega328P flash via optiboot STK500v1.
 *
 * Performs: auto-reset (DTR pulse) -> get_sync -> get_signature -> enter_progmode
 *           -> loop (load_address + prog_page) -> leave_progmode.
 * Blocks the calling task for the full flash duration (~8s for 32KB).
 * The caller MUST have claimed USB RX first (usb_host_rx_claim()).
 *
 * @param buffer    Raw binary flash image (must be <= 32768 bytes)
 * @param size      Size in bytes
 * @param page_size Page size (typically 128 for ATmega328P)
 * @return true if all pages written & signature verified
 */
bool stk500v1_flash_buffer(const uint8_t *buffer, size_t size, uint16_t page_size);
