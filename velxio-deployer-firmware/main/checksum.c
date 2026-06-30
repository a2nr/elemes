#include "checksum.h"

static uint32_t crc32_table[256];
static int table_initialized = 0;

static void crc32_init_table(void)
{
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t c = i;
        for (int j = 0; j < 8; j++) {
            c = (c & 1) ? (0xEDB88320 ^ (c >> 1)) : (c >> 1);
        }
        crc32_table[i] = c;
    }
    table_initialized = 1;
}

uint32_t checksum_crc32(const uint8_t *data, size_t len)
{
    if (!table_initialized) {
        crc32_init_table();
    }
    if (!data || len == 0) return 0;

    uint32_t crc = 0xFFFFFFFF;
    for (size_t i = 0; i < len; i++) {
        crc = crc32_table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
    }
    return crc ^ 0xFFFFFFFF;
}
