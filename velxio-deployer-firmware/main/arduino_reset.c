#include "arduino_reset.h"
#include "usb_host.h"
#include "esp_log.h"

static const char *TAG = "ARDUINO_RESET";

/**
 * Trigger DTR pulse to reset Arduino.
 * Delegates to the existing usb_host_reset_arduino() which drives
 * DTR/RTS low → 1ms delay → high → 50ms delay, mirroring avrdude's
 * Arduino autoreset sequence.
 */
void arduino_trigger_reset(void) {
    ESP_LOGI(TAG, "Triggering Arduino reset via DTR pulse...");
    usb_host_reset_arduino();
    ESP_LOGI(TAG, "Arduino reset pulse complete");
}
