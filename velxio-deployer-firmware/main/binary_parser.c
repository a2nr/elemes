#include <string.h>
#include <inttypes.h>
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "binary_parser.h"
#include "checksum.h"
#include "ble_service.h"

static const char *TAG = "BIN_PARSER";

static parser_state_t state = PARSER_IDLE;
static uint8_t *hex_buffer = NULL;
static size_t buffer_offset = 0;
static size_t buffer_size = 0;
static uint32_t expected_total_crc = 0;
static int total_chunks = 0;
static int received_chunks = 0;

void binary_parser_init(void)
{
    hex_buffer = (uint8_t *)heap_caps_malloc(MAX_HEX_SIZE, MALLOC_CAP_SPIRAM);
    if (hex_buffer) {
        ESP_LOGI(TAG, "PSRAM buffer allocated: %d bytes at %p", MAX_HEX_SIZE, hex_buffer);
    } else {
        ESP_LOGE(TAG, "Failed to allocate PSRAM buffer!");
        hex_buffer = malloc(MAX_HEX_SIZE);
        if (hex_buffer) {
            ESP_LOGW(TAG, "Fallback to SRAM buffer: %d bytes", MAX_HEX_SIZE);
        }
    }
}

parser_state_t binary_parser_process_packet(uint8_t *payload, size_t len)
{
    if (len < 8) return PARSER_ERROR;
    if (!hex_buffer) return PARSER_ERROR;

    uint8_t cmd = payload[0];
    uint16_t index = payload[1] | (payload[2] << 8);
    uint8_t data_len = payload[3];

    if (4 + data_len + 4 > len) return PARSER_ERROR;

    uint8_t *data = payload + 4;
    uint32_t received_crc = (uint32_t)payload[4 + data_len] |
                            ((uint32_t)payload[4 + data_len + 1] << 8) |
                            ((uint32_t)payload[4 + data_len + 2] << 16) |
                            ((uint32_t)payload[4 + data_len + 3] << 24);

    switch (cmd) {
    case CMD_INIT: {
        if (data_len >= 4) {
            expected_total_crc = (uint32_t)data[0] |
                                 ((uint32_t)data[1] << 8) |
                                 ((uint32_t)data[2] << 16) |
                                 ((uint32_t)data[3] << 24);
        }
        buffer_offset = 0;
        buffer_size = 0;
        received_chunks = 0;
        total_chunks = 0;
        state = PARSER_RECEIVING;
        ESP_LOGI(TAG, "INIT: expected total CRC = 0x%08lX", (unsigned long)expected_total_crc);

        /* Echo the received index so the webapp can distinguish INIT ACK
         * from DATA chunk-0 ACK (both would be index 0 if hardcoded).
         * Webapp sends INIT with INIT_ACK_INDEX (0xFFFE) for uniqueness. */
        uint8_t ack[] = {CMD_ACK, index & 0xFF, (index >> 8) & 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00};
        ble_service_send_notify_flashing(ack, sizeof(ack));
        break;
    }

    case CMD_DATA: {
        if (state != PARSER_RECEIVING) return PARSER_ERROR;

        uint32_t chunk_crc = checksum_crc32(data, data_len);
        if (chunk_crc != received_crc) {
            ESP_LOGE(TAG, "CRC mismatch chunk %d: expected 0x%08lX, got 0x%08lX",
                     index, (unsigned long)received_crc, (unsigned long)chunk_crc);
            uint8_t err[] = {CMD_ERR, index & 0xFF, (index >> 8) & 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00};
            ble_service_send_notify_flashing(err, sizeof(err));
            return PARSER_ERROR;
        }

        if (buffer_offset + data_len <= MAX_HEX_SIZE) {
            memcpy(hex_buffer + buffer_offset, data, data_len);
            buffer_offset += data_len;
            received_chunks++;
        } else {
            ESP_LOGE(TAG, "Buffer overflow!");
            state = PARSER_ERROR;
            return PARSER_ERROR;
        }

        uint8_t ack[] = {CMD_ACK, index & 0xFF, (index >> 8) & 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00};
        ble_service_send_notify_flashing(ack, sizeof(ack));
        break;
    }

    case CMD_END: {
        buffer_size = buffer_offset;
        state = PARSER_COMPLETE;
        ESP_LOGI(TAG, "END: %d bytes in %d chunks, buffer_size=%d",
                 buffer_size, received_chunks, (int)buffer_size);
        break;
    }

    default:
        return PARSER_ERROR;
    }

    return state;
}

uint32_t binary_parser_get_total_crc(void)
{
    return expected_total_crc;
}

uint8_t *binary_parser_get_buffer(void)
{
    return hex_buffer;
}

size_t binary_parser_get_buffer_size(void)
{
    return buffer_size;
}

void binary_parser_reset(void)
{
    state = PARSER_IDLE;
    buffer_offset = 0;
    buffer_size = 0;
    received_chunks = 0;
    total_chunks = 0;
    expected_total_crc = 0;
}

parser_state_t binary_parser_get_state(void)
{
    return state;
}
