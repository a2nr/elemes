/**
 * @file binary_parser.h
 * @brief Binary payload parser for the BLE flashing protocol.
 *
 * Implements the 4-command protocol:
 *   INIT (0x01) — start transfer, receive expected total CRC
 *   DATA (0x02) — chunk of hex binary with per-chunk CRC32
 *   END  (0x03) — finalise, verify accumulated CRC against expected
 *   ACK  (0x04) — acknowledgement (sent by firmware)
 *   ERR  (0x05) — error indication (sent by firmware)
 *
 * Payload format: [CMD:1][Index:2][Len:1][Data:N][CRC32:4]
 *
 * Buffer allocated in PSRAM via heap_caps_malloc(MALLOC_CAP_SPIRAM).
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

#define CMD_INIT 0x01
#define CMD_DATA 0x02
#define CMD_END  0x03
#define CMD_ACK  0x04
#define CMD_ERR  0x05
#define CMD_SET_BAUD 0x06

/** Maximum hex binary buffer size (256 KB — fits largest Arduino sketch). */
#define MAX_HEX_SIZE (256 * 1024)

/** Parser finite state. */
typedef enum {
    PARSER_IDLE,      /**< Waiting for INIT. */
    PARSER_RECEIVING, /**< Actively receiving DATA chunks. */
    PARSER_COMPLETE,  /**< All data received and CRC verified. */
    PARSER_ERROR      /**< CRC mismatch or protocol violation. */
} parser_state_t;

/**
 * @brief Single binary packet descriptor (for inspection/debugging).
 */
typedef struct {
    uint8_t command;   /**< CMD_INIT / CMD_DATA / CMD_END */
    uint16_t index;    /**< Chunk index (little-endian) */
    uint8_t length;    /**< Number of data bytes in this packet */
    uint8_t *data;     /**< Pointer to data portion */
    uint32_t crc32;    /**< CRC32 value from packet trailer */
} binary_packet_t;

void binary_parser_init(void);
parser_state_t binary_parser_process_packet(uint8_t *payload, size_t len);
uint32_t binary_parser_get_total_crc(void);
uint8_t *binary_parser_get_buffer(void);
size_t binary_parser_get_buffer_size(void);
void binary_parser_reset(void);
parser_state_t binary_parser_get_state(void);
