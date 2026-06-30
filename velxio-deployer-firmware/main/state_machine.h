/**
 * @file state_machine.h
 * @brief Finite state machine orchestrating the deploy lifecycle.
 *
 * States:
 *   IDLE -> RECEIVING -> VERIFYING -> FLASHING -> SERIAL_BRIDGE
 *                                                         |
 *   ERROR_CHECKSUM <--- VERIFY_FAIL                      |
 *   ERROR_TARGET   <--- FLASH_FAIL / USB_DISCONNECT <----+
 *
 * Transitions are driven by events from BLE, USB, and the button.
 *
 * Flashing runs in a dedicated flasher_task (created in state_machine_init),
 * so the BLE host thread is never blocked for the ~8s flash duration. The
 * VERIFYING -> FLASHING transition hands off via flasher_sem; the flasher
 * task posts EVENT_FLASH_OK / EVENT_FLASH_FAIL back into the SM when done.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

/** System states. */
typedef enum {
    STATE_IDLE,            /**< Waiting for BLE INIT command */
    STATE_RECEIVING,       /**< Receiving binary chunks via BLE */
    STATE_VERIFYING,       /**< CRC32 verification of accumulated buffer */
    STATE_FLASHING,        /**< Programming Arduino via STK500v1 */
    STATE_SERIAL_BRIDGE,   /**< Transparent CDC <-> BLE bridge active */
    STATE_ERROR_TARGET,    /**< USB/STK500 failure — LED red, wait for Retry */
    STATE_ERROR_CHECKSUM   /**< CRC mismatch — LED red blink, wait for Retry */
} deployer_state_t;

/** Events that trigger state transitions. */
typedef enum {
    EVENT_BLE_INIT,        /**< Received INIT command from BLE */
    EVENT_BLE_DATA,        /**< Received DATA chunk (internal) */
    EVENT_BLE_END,         /**< Received END command */
    EVENT_VERIFY_OK,       /**< CRC32 verification passed */
    EVENT_VERIFY_FAIL,     /**< CRC32 verification failed */
    EVENT_FLASH_OK,        /**< STK500v1 flashing succeeded (posted by flasher task) */
    EVENT_FLASH_FAIL,      /**< STK500v1 flashing failed (posted by flasher task) */
    EVENT_BUTTON_RETRY,    /**< Physical Retry button pressed */
    EVENT_BLE_DISCONNECT,  /**< BLE link lost */
    EVENT_USB_DISCONNECT   /**< Arduino USB disconnected */
} sm_event_t;

void state_machine_init(void);
void state_machine_process_event(sm_event_t event, void *data);
deployer_state_t state_machine_get_current(void);
const char *state_machine_get_state_name(void);
void state_machine_tick(void);
