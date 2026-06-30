/**
 * @file checksum.h
 * @brief CRC32 checksum with pre-computed lookup table.
 *
 * Uses the standard IEEE 802.3 polynomial (0xEDB88320).
 * Table is initialised on first call, cached for subsequent calls.
 */

#pragma once

#include <stdint.h>
#include <stddef.h>

/**
 * @brief Compute CRC32 over a memory buffer.
 * @param data  Pointer to input bytes
 * @param len   Number of bytes
 * @return CRC32 value (reflected, final XOR 0xFFFFFFFF)
 */
uint32_t checksum_crc32(const uint8_t *data, size_t len);
