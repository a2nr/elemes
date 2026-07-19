#include <string.h>
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "stk500v1.h"
#include "usb_host.h"

static const char *TAG = "STK500";

/* Read exactly resp_len bytes within timeout_ms. Returns true on success. */
static bool read_exact(uint8_t *buf, size_t resp_len, uint32_t timeout_ms)
{
    size_t got = 0;
    int64_t deadline = esp_timer_get_time() + (int64_t)timeout_ms * 1000;

    while (got < resp_len) {
        int64_t remaining_us = deadline - esp_timer_get_time();
        if (remaining_us <= 0) {
            ESP_LOGE(TAG, "read_exact timeout: got %d/%d", (int)got, (int)resp_len);
            return false;
        }
        uint32_t chunk_to = (uint32_t)((remaining_us + 999) / 1000);
        if (chunk_to == 0) chunk_to = 1;

        int n = usb_host_read_cdc(buf + got, resp_len - got, chunk_to);
        if (n < 0) {
            ESP_LOGD(TAG, "read_exact: got %d/%d (n=%d)", (int)got, (int)resp_len, n);
            if (!usb_host_arduino_connected()) {
                ESP_LOGE(TAG, "read_exact: device disconnected mid-read");
                return false;
            }
            continue;
        }
        if (n > 0) {
            got += (size_t)n;
        }
    }
    return true;
}

/* Send a command (already includes CRC_EOP), then expect STK_INSYNC and
 * optional payload + STK_OK. strict_ok=true requires the trailing STK_OK. */
static bool send_and_expect(const uint8_t *cmd, size_t cmd_len,
                            uint8_t *resp, size_t resp_len,
                            uint32_t timeout_ms, bool strict_ok)
{
    if (!usb_host_write_cdc(cmd, cmd_len)) {
        ESP_LOGE(TAG, "send failed (%d bytes)", (int)cmd_len);
        return false;
    }

    uint8_t insync = 0;
    if (!read_exact(&insync, 1, timeout_ms)) {
        ESP_LOGE(TAG, "no INSYNC (got 0x%02X)", insync);
        return false;
    }
    if (insync == STK_NOSYNC) {
        ESP_LOGE(TAG, "optiboot replied NOSYNC");
        return false;
    }
    if (insync != STK_INSYNC) {
        ESP_LOGE(TAG, "expected INSYNC 0x14, got 0x%02X", insync);
        return false;
    }

    if (resp && resp_len > 0) {
        if (!read_exact(resp, resp_len, timeout_ms)) {
            ESP_LOGE(TAG, "payload read failed (%d bytes)", (int)resp_len);
            return false;
        }
    }

    if (strict_ok) {
        uint8_t ok = 0;
        if (!read_exact(&ok, 1, timeout_ms)) {
            ESP_LOGE(TAG, "no STK_OK");
            return false;
        }
        if (ok != STK_OK) {
            ESP_LOGE(TAG, "expected OK 0x10, got 0x%02X", ok);
            return false;
        }
    }
    return true;
}

bool stk500v1_init(void)
{
    esp_log_level_set(TAG, ESP_LOG_DEBUG);
    ESP_LOGI(TAG, "STK500v1 layer initialised (optiboot / ATmega328P)");
    return true;
}

static bool cmd_get_sync(void)
{
    uint8_t cmd[] = { STK_GET_SYNC, STK_CRC_EOP };

    for (int attempt = 0; attempt < STK_SYNC_RETRIES; attempt++) {
        ESP_LOGI(TAG, "get_sync attempt %d/%d: sending 0x30 0x20", attempt + 1, STK_SYNC_RETRIES);
        if (send_and_expect(cmd, sizeof(cmd), NULL, 0,
                            STK_CMD_TIMEOUT_MS, true)) {
            ESP_LOGI(TAG, "get_sync OK after %d attempt(s)", attempt + 1);
            return true;
        }
        /* Drain any stray bytes before retrying. */
        uint8_t drain[32];
        int drained = usb_host_read_cdc(drain, sizeof(drain), 30);
        if (drained > 0) {
            ESP_LOGW(TAG, "drained %d bytes after attempt %d: first=0x%02X", drained, attempt + 1, drain[0]);
        }
        uint32_t backoff = (20u << attempt);
        if (backoff > 150u) backoff = 150u;
        vTaskDelay(pdMS_TO_TICKS(backoff));
    }
    ESP_LOGE(TAG, "get_sync failed after %d attempts", STK_SYNC_RETRIES);
    return false;
}

static bool cmd_get_signature(uint8_t sig[3])
{
    uint8_t cmd[] = { STK_READ_SIGN, STK_CRC_EOP };
    uint8_t resp[3] = {0};

    if (!send_and_expect(cmd, sizeof(cmd), resp, sizeof(resp),
                         STK_CMD_TIMEOUT_MS, true)) {
        return false;
    }
    sig[0] = resp[0];
    sig[1] = resp[1];
    sig[2] = resp[2];
    ESP_LOGI(TAG, "signature: %02X %02X %02X", sig[0], sig[1], sig[2]);
    return true;
}

static bool cmd_enter_progmode(void)
{
    uint8_t cmd[] = { STK_ENTER_PROGMODE, STK_CRC_EOP };
    return send_and_expect(cmd, sizeof(cmd), NULL, 0,
                           STK_CMD_TIMEOUT_MS, true);
}

static bool cmd_load_address(uint16_t word_addr)
{
    uint8_t cmd[] = {
        STK_LOAD_ADDRESS,
        (uint8_t)(word_addr & 0xFF),
        (uint8_t)((word_addr >> 8) & 0xFF),
        STK_CRC_EOP
    };
    return send_and_expect(cmd, sizeof(cmd), NULL, 0,
                           STK_CMD_TIMEOUT_MS, true);
}

static bool cmd_prog_page(const uint8_t *data, uint16_t len)
{
    /* Header: 0x64, len_hi, len_lo, memtype 'F'(0x46). Then data, then EOP. */
    uint8_t header[4] = {
        STK_PROG_PAGE,
        (uint8_t)((len >> 8) & 0xFF),
        (uint8_t)(len & 0xFF),
        0x46  /* 'F' = flash */
    };

    /* Send header + data + EOP as one logical transfer. CherryUSB write is
     * a single URB, so we build a contiguous buffer. */
    static uint8_t pkt[4 + ATMEGA328P_PAGE_SIZE + 1];
    if (len > ATMEGA328P_PAGE_SIZE) {
        ESP_LOGE(TAG, "prog_page len %d exceeds page %d", len, ATMEGA328P_PAGE_SIZE);
        return false;
    }
    memcpy(pkt, header, 4);
    memcpy(pkt + 4, data, len);
    pkt[4 + len] = STK_CRC_EOP;

    return send_and_expect(pkt, 4 + len + 1, NULL, 0,
                           STK_PAGE_TIMEOUT_MS, true);
}

static bool cmd_leave_progmode(void)
{
    uint8_t cmd[] = { STK_LEAVE_PROGMODE, STK_CRC_EOP };
    /* optiboot shortens WDT and resets; STK_OK may be absent. Lenient. */
    bool ok = send_and_expect(cmd, sizeof(cmd), NULL, 0,
                              STK_LEAVE_TIMEOUT_MS, false);
    if (!ok) {
        ESP_LOGW(TAG, "leave_progmode did not reply (expected on optiboot)");
        /* Treat as success — optiboot intentionally resets. */
        ok = true;
    }
    return ok;
}

bool stk500v1_flash_buffer(const uint8_t *buffer, size_t size, uint16_t page_size)
{
    if (!buffer || size == 0) {
        ESP_LOGE(TAG, "flash_buffer: null/empty buffer");
        return false;
    }
    if (page_size == 0) {
        ESP_LOGE(TAG, "flash_buffer: page_size=0");
        return false;
    }
    if (size > ATMEGA328P_FLASH_SIZE) {
        ESP_LOGE(TAG, "flash_buffer: size %d exceeds flash %d",
                 (int)size, ATMEGA328P_FLASH_SIZE);
        return false;
    }
    if (page_size != ATMEGA328P_PAGE_SIZE) {
        ESP_LOGW(TAG, "page_size %d != expected %d — using provided",
                 page_size, ATMEGA328P_PAGE_SIZE);
    }

    ESP_LOGI(TAG, "Starting flash: %d bytes, page %d", (int)size, page_size);

    /* 1. Auto-reset Arduino to (re)enter optiboot. */
    if (!usb_host_arduino_connected()) {
        ESP_LOGE(TAG, "flash_buffer: Arduino not connected — abort before reset");
        return false;
    }
    usb_host_reset_arduino();

    /* 1b. Drain any stale bytes left in CDC ringbuffer from prior serial bridge session. */
    usb_host_drain_cdc(256, 50);

    /* 2. Get sync (retry within optiboot ~1s window). */
    if (!cmd_get_sync()) {
        return false;
    }

    /* 3. Read & validate signature. */
    uint8_t sig[3] = {0};
    if (!cmd_get_signature(sig)) {
        return false;
    }
    if (sig[0] != ATMEGA328P_SIG_0 || sig[1] != ATMEGA328P_SIG_1 ||
        sig[2] != ATMEGA328P_SIG_2) {
        ESP_LOGE(TAG, "signature mismatch: got %02X %02X %02X, want %02X %02X %02X",
                 sig[0], sig[1], sig[2],
                 ATMEGA328P_SIG_0, ATMEGA328P_SIG_1, ATMEGA328P_SIG_2);
        return false;
    }

    /* 4. Enter programming mode. */
    if (!cmd_enter_progmode()) {
        ESP_LOGE(TAG, "enter_progmode failed");
        return false;
    }
    ESP_LOGI(TAG, "entered programming mode");

    /* 5. Program pages. ATmega328P uses word addresses (byte/2). */
    uint16_t pages = (uint16_t)((size + page_size - 1) / page_size);
    for (uint16_t page = 0; page < pages; page++) {
        uint16_t byte_addr = (uint16_t)(page * page_size);
        uint16_t word_addr = byte_addr / 2;
        uint16_t remaining = (uint16_t)(size - byte_addr);
        uint16_t this_len = (remaining > page_size) ? page_size : remaining;

        if (!cmd_load_address(word_addr)) {
            ESP_LOGE(TAG, "load_address failed at page %d (word 0x%04X)",
                     page + 1, word_addr);
            cmd_leave_progmode();
            return false;
        }
        if (!cmd_prog_page(buffer + byte_addr, this_len)) {
            ESP_LOGE(TAG, "prog_page failed at page %d/%d (byte 0x%04X, %d bytes)",
                     page + 1, pages, byte_addr, this_len);
            cmd_leave_progmode();
            return false;
        }

        if ((page + 1) % 16 == 0 || page + 1 == pages) {
            ESP_LOGI(TAG, "flashing page %d/%d", page + 1, pages);
        }
        /* Yield to keep BLE host stack alive. */
        vTaskDelay(pdMS_TO_TICKS(1));
    }

    /* 6. Leave programming mode. */
    cmd_leave_progmode();

    ESP_LOGI(TAG, "Flash complete: %d pages written", pages);
    return true;
}
