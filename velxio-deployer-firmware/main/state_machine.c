#include <string.h>
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "state_machine.h"
#include "binary_parser.h"
#include "checksum.h"
#include "usb_host.h"
#include "stk500v1.h"
#include "serial_bridge.h"
#include "led_button.h"
#include "ble_service.h"

static const char *TAG = "SM";

static deployer_state_t current_state = STATE_IDLE;
static uint16_t stk500_page_size = 128;

/* Flasher task: blocks on flasher_sem, runs stk500v1 off the BLE thread. */
static SemaphoreHandle_t flasher_sem = NULL;
static TaskHandle_t flasher_task_handle = NULL;

/* Snapshot of the buffer to flash (valid only while in STATE_FLASHING). */
static const uint8_t *flasher_buffer = NULL;
static size_t flasher_size = 0;

static void flasher_task(void *arg)
{
    while (1) {
        xSemaphoreTake(flasher_sem, portMAX_DELAY);

        ESP_LOGI(TAG, "Flasher task started: %d bytes", (int)flasher_size);

        /* Claim USB RX so STK500 can read CDC responses exclusively. */
        usb_host_rx_claim();

        bool ok = stk500v1_flash_buffer(flasher_buffer, flasher_size,
                                        stk500_page_size);

        usb_host_rx_release();

        ESP_LOGI(TAG, "Flasher task done: %s", ok ? "OK" : "FAIL");
        state_machine_process_event(ok ? EVENT_FLASH_OK : EVENT_FLASH_FAIL,
                                     NULL);
    }
}

void state_machine_init(void)
{
    current_state = STATE_IDLE;
    esp_log_level_set(TAG, ESP_LOG_DEBUG);

    flasher_sem = xSemaphoreCreateBinary();
    if (!flasher_sem) {
        ESP_LOGE(TAG, "Failed to create flasher_sem");
        return;
    }

    BaseType_t r = xTaskCreate(flasher_task, "flasher", 8192, NULL, 4,
                               &flasher_task_handle);
    if (r != pdPASS) {
        ESP_LOGE(TAG, "Failed to create flasher task");
    }

    ESP_LOGI(TAG, "State machine initialized: IDLE (flasher task ready)");
}

void state_machine_process_event(sm_event_t event, void *data)
{
    ESP_LOGD(TAG, "Event: %d in state: %s", event, state_machine_get_state_name());

    /* ACK unique index for END: 0xFFFF so the webapp can disambiguate from INIT (index=0). */
    static const uint16_t END_ACK_INDEX = 0xFFFF;

    switch (current_state) {
    case STATE_IDLE:
    	if (event == EVENT_BLE_INIT) {
    		current_state = STATE_RECEIVING;
    		led_set_pattern(LED_BLUE_BLINK);
    		ESP_LOGI(TAG, "Transition: IDLE -> RECEIVING");
    	}
    	break;

    case STATE_RECEIVING:
    	if (event == EVENT_BLE_END) {
    		current_state = STATE_VERIFYING;
    		ESP_LOGI(TAG, "Transition: RECEIVING -> VERIFYING");
    		state_machine_process_event(EVENT_VERIFY_OK, NULL);
    	} else if (event == EVENT_BLE_INIT) {
    		ESP_LOGE(TAG, "Unexpected INIT in RECEIVING state");
    	} else if (event == EVENT_BLE_DISCONNECT) {
    		ESP_LOGI(TAG, "BLE disconnect in RECEIVING, resetting to IDLE");
    		binary_parser_reset();
    		current_state = STATE_IDLE;
    		led_set_pattern(LED_BLUE_BLINK);
    	}
    	break;

    case STATE_VERIFYING:
    	if (event == EVENT_VERIFY_OK) {
    		uint32_t expected_crc = binary_parser_get_total_crc();
    		uint8_t *buffer = binary_parser_get_buffer();
    		size_t size = binary_parser_get_buffer_size();
    		uint32_t actual_crc = checksum_crc32(buffer, size);

    		if (actual_crc == expected_crc) {
    			ESP_LOGI(TAG, "CRC verification OK: 0x%08X", actual_crc);
    			current_state = STATE_FLASHING;
    			led_set_pattern(LED_BLUE);

    			/* Hand off to flasher task instead of blocking the BLE
    			 * thread. Snapshot buffer ptr/size — parser won't mutate
    			 * them until next INIT (which can't happen in FLASHING). */
    			flasher_buffer = buffer;
    			flasher_size = size;
    			xSemaphoreGive(flasher_sem);
    			ESP_LOGI(TAG, "Transition: VERIFYING -> FLASHING (flasher armed)");
    		} else {
    			ESP_LOGE(TAG, "CRC verification FAILED: expected 0x%08X, got 0x%08X",
    			         expected_crc, actual_crc);
    			state_machine_process_event(EVENT_VERIFY_FAIL, NULL);
    		}
    	} else if (event == EVENT_VERIFY_FAIL) {
    		current_state = STATE_ERROR_CHECKSUM;
    		led_set_pattern(LED_RED_BLINK);

    		uint8_t err[] = {CMD_ERR, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00, 0x00};
    		memcpy(err + 4, "CRC MISMATCH", 12);
    		ble_service_send_notify_flashing(err, sizeof(err));
    		ESP_LOGI(TAG, "Transition: VERIFYING -> ERROR_CHECKSUM");
    	} else if (event == EVENT_BLE_DISCONNECT) {
    		ESP_LOGI(TAG, "BLE disconnect in VERIFYING, resetting to IDLE");
    		binary_parser_reset();
    		current_state = STATE_IDLE;
    		led_set_pattern(LED_BLUE_BLINK);
    	}
    	break;

    case STATE_FLASHING:
    	if (event == EVENT_FLASH_OK) {
    		/* Flasher task completed successfully — send ACK to webapp. */
    		current_state = STATE_SERIAL_BRIDGE;
    		led_set_pattern(LED_GREEN);
    		serial_bridge_start();

    		uint8_t ack[] = {CMD_ACK,
    		                 END_ACK_INDEX & 0xFF,
    		                 (END_ACK_INDEX >> 8) & 0xFF,
    		                 0x00, 0x00, 0x00, 0x00, 0x00};
    		ble_service_send_notify_flashing(ack, sizeof(ack));
    		ESP_LOGI(TAG, "Transition: FLASHING -> SERIAL_BRIDGE");
    	} else if (event == EVENT_FLASH_FAIL) {
    		current_state = STATE_ERROR_TARGET;
    		led_set_pattern(LED_RED);

    		uint8_t err[] = {CMD_ERR, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00, 0x00};
    		memcpy(err + 4, "FLASH FAILED", 12);
    		ble_service_send_notify_flashing(err, sizeof(err));
    		ESP_LOGI(TAG, "Transition: FLASHING -> ERROR_TARGET");
    	} else if (event == EVENT_BLE_DISCONNECT) {
    		ESP_LOGW(TAG, "BLE disconnect during FLASHING — flasher will finish, SM reset to IDLE");
    		current_state = STATE_IDLE;
    		led_set_pattern(LED_BLUE_BLINK);
    	}
    	break;

    case STATE_SERIAL_BRIDGE:
        if (event == EVENT_BLE_INIT) {
            serial_bridge_stop();
            binary_parser_reset();
            current_state = STATE_RECEIVING;
            led_set_pattern(LED_BLUE_BLINK);
            ESP_LOGI(TAG, "Transition: SERIAL_BRIDGE -> RECEIVING (re-deploy)");
        } else if (event == EVENT_BLE_DISCONNECT || event == EVENT_USB_DISCONNECT) {
            serial_bridge_stop();
            current_state = STATE_ERROR_TARGET;
            led_set_pattern(LED_RED);
            ESP_LOGI(TAG, "Transition: SERIAL_BRIDGE -> ERROR_TARGET (disconnect)");
        }
        break;

    case STATE_ERROR_TARGET:
    case STATE_ERROR_CHECKSUM:
        if (event == EVENT_BLE_INIT) {
            ESP_LOGI(TAG, "Re-deploy from ERROR state — transition to RECEIVING");
            serial_bridge_stop();
            binary_parser_reset();
            current_state = STATE_RECEIVING;
            led_set_pattern(LED_BLUE_BLINK);
        } else if (event == EVENT_BUTTON_RETRY) {
            ESP_LOGI(TAG, "Button retry pressed, resetting to IDLE");
            binary_parser_reset();
            serial_bridge_stop();
            current_state = STATE_IDLE;
            led_set_pattern(LED_BLUE_BLINK);
        } else if (event == EVENT_BLE_DISCONNECT) {
            current_state = STATE_IDLE;
            led_set_pattern(LED_BLUE_BLINK);
            ESP_LOGI(TAG, "Transition: ERROR -> IDLE (BLE disconnect)");
        }
        break;
    }
}

deployer_state_t state_machine_get_current(void)
{
    return current_state;
}

const char *state_machine_get_state_name(void)
{
    switch (current_state) {
    case STATE_IDLE:          return "IDLE";
    case STATE_RECEIVING:     return "RECEIVING";
    case STATE_VERIFYING:     return "VERIFYING";
    case STATE_FLASHING:      return "FLASHING";
    case STATE_SERIAL_BRIDGE: return "SERIAL_BRIDGE";
    case STATE_ERROR_TARGET:  return "ERROR_TARGET";
    case STATE_ERROR_CHECKSUM: return "ERROR_CHECKSUM";
    default:                  return "UNKNOWN";
    }
}

void state_machine_tick(void)
{
    if (current_state == STATE_SERIAL_BRIDGE) {
        if (!usb_host_arduino_connected()) {
            state_machine_process_event(EVENT_USB_DISCONNECT, NULL);
        }
    }

    if ((current_state == STATE_ERROR_TARGET || current_state == STATE_ERROR_CHECKSUM)) {
        if (button_retry_pressed()) {
            state_machine_process_event(EVENT_BUTTON_RETRY, NULL);
        }
    }
}
