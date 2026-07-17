#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "esp_bt.h"

#include "ble_service.h"
#include "binary_parser.h"
#include "checksum.h"
#include "usb_host.h"
#include "stk500v1.h"
#include "state_machine.h"
#include "serial_bridge.h"
#include "led_button.h"
#include "device_name.h"
#include "wifi_ap.h"

static const char *TAG = "MAIN";

static void on_ble_flashing_data(uint8_t *data, size_t len)
{
    if (len < 4) return;

    uint8_t cmd = data[0];

    switch (cmd) {
    case CMD_INIT: {
        ESP_LOGI(TAG, "Received INIT command");
        serial_bridge_stop();
        binary_parser_process_packet(data, len);
        state_machine_process_event(EVENT_BLE_INIT, data);
        break;
    }
    case CMD_DATA: {
        parser_state_t result = binary_parser_process_packet(data, len);
        if (result == PARSER_ERROR) {
            ESP_LOGE(TAG, "Packet parse error");
            state_machine_process_event(EVENT_VERIFY_FAIL, NULL);
        }
        break;
    }
    case CMD_END: {
        ESP_LOGI(TAG, "Received END command");
        binary_parser_process_packet(data, len);
        state_machine_process_event(EVENT_BLE_END, data);
        break;
    }
    default:
        ESP_LOGW(TAG, "Unknown command: 0x%02X", cmd);
        break;
    }
}

static void on_usb_serial_data(uint8_t *data, size_t len)
{
    serial_bridge_on_usb_data(data, len);
}

static void on_ble_serial_data(uint8_t *data, size_t len)
{
    if (serial_bridge_is_active()) {
        usb_host_write_cdc(data, len);
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "Velxio BLE Deployer v1.0");

    // Initialize NVS
    nvs_flash_init();

    // Initialize device name from NVS or MAC suffix
    device_name_init();

    // AP setup mode: if no custom name, start AP config portal
    if (!device_name_is_custom()) {
        ESP_LOGW(TAG, "No custom name — entering AP setup mode");
        wifi_ap_start_and_block();  // never returns
    }

    // --- Normal boot: BLE + USB Host mode ---

    esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);

    led_button_init();
    checksum_crc32(NULL, 0);
    binary_parser_init();
    ble_service_init();
    ble_service_set_flashing_callback(on_ble_flashing_data);
    ble_service_set_serial_callback(on_ble_serial_data);

    usb_host_init();
    usb_host_set_serial_callback(on_usb_serial_data);

    led_set_pattern(LED_BLUE_BLINK_SLOW);

    state_machine_init();

    while (1) {
        state_machine_tick();
        serial_bridge_tick();
        led_button_tick();
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
