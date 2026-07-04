#include <string.h>
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "serial_bridge.h"
#include "ble_service.h"
#include "usb_host.h"

static const char *TAG = "SERIAL_BRIDGE";

static bool active = false;
static int64_t last_flush_time = 0;
static int notify_count = 0;
static int64_t rate_window_start = 0;

#define BRIDGE_BUF_SIZE 240
#define MAX_NOTIFY_RATE 20
#define RATE_WINDOW_MS 1000
#define THROTTLE_INTERVAL_MS 50
#define BUFFER_FLUSH_MS 500

static uint8_t bridge_buf[BRIDGE_BUF_SIZE];
static size_t bridge_buf_len = 0;

void serial_bridge_init(void)
{
    active = false;
    bridge_buf_len = 0;
    last_flush_time = 0;
    notify_count = 0;
    rate_window_start = 0;
    ESP_LOGI(TAG, "Serial bridge initialized");
}

void serial_bridge_start(void)
{
    active = true;
    bridge_buf_len = 0;
    last_flush_time = esp_timer_get_time() / 1000;
    notify_count = 0;
    rate_window_start = esp_timer_get_time() / 1000;
    ESP_LOGI(TAG, "Serial bridge started");
}

void serial_bridge_stop(void)
{
    /* Flush any remaining buffered data before stopping. */
    if (active && bridge_buf_len > 0) {
        ble_service_send_notify_serial(bridge_buf, bridge_buf_len);
        bridge_buf_len = 0;
    }
    active = false;
    ESP_LOGI(TAG, "Serial bridge stopped");
}

bool serial_bridge_is_active(void)
{
    return active;
}

void serial_bridge_on_ble_write(uint8_t *data, size_t len)
{
    if (!active) return;
    usb_host_write_cdc(data, len);
}

void serial_bridge_on_usb_data(uint8_t *data, size_t len)
{
    if (!active) return;

    ESP_LOGI(TAG, "USB->BLE: %d bytes, buf=%d/%d", len, bridge_buf_len, BRIDGE_BUF_SIZE);

    /* Large packet: flush buffer first, then chunk into MTU-sized pieces. */
    size_t remaining = BRIDGE_BUF_SIZE - bridge_buf_len;
    if (len >= BRIDGE_BUF_SIZE) {
        if (bridge_buf_len > 0) {
            ble_service_send_notify_serial(bridge_buf, bridge_buf_len);
            bridge_buf_len = 0;
        }
        size_t offset = 0;
        while (offset < len) {
            size_t chunk = (len - offset > BRIDGE_BUF_SIZE) ? BRIDGE_BUF_SIZE : (len - offset);
            ble_service_send_notify_serial(data + offset, chunk);
            offset += chunk;
            vTaskDelay(1);
        }
        return;
    }

    /* Buffer nearly full: flush first. */
    if (len > remaining) {
        ble_service_send_notify_serial(bridge_buf, bridge_buf_len);
        bridge_buf_len = 0;
    }

    memcpy(bridge_buf + bridge_buf_len, data, len);
    bridge_buf_len += len;
}

void serial_bridge_tick(void)
{
    if (!active || bridge_buf_len == 0) return;

    int64_t now = esp_timer_get_time() / 1000;

    /* Reset rate counter every second. */
    if (now - rate_window_start >= RATE_WINDOW_MS) {
        rate_window_start = now;
        notify_count = 0;
    }

    int64_t since_flush = now - last_flush_time;
    bool time_to_flush = (since_flush >= THROTTLE_INTERVAL_MS) &&
                         (notify_count < MAX_NOTIFY_RATE);
    bool stale = since_flush >= BUFFER_FLUSH_MS;

    if (time_to_flush || stale) {
        ESP_LOGI(TAG, "flush: %d bytes, notify#%d%s", bridge_buf_len, notify_count, stale ? " (stale)" : "");
        ble_service_send_notify_serial(bridge_buf, bridge_buf_len);
        bridge_buf_len = 0;
        last_flush_time = now;
        notify_count++;
    }
}
