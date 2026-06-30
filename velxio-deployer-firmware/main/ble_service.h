/**
 * @file ble_service.h
 * @brief BLE Peripheral service using NimBLE stack.
 *
 * Manages advertising, connection, and two custom GATT characteristics:
 * - Flashing (Write with Response + Notify): for binary payload transfer
 * - Serial   (Write Without Response + Notify): for transparent UART bridge
 *
 * Service UUID: 56454c58-494f-0000-0000-000000000001
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

#define BLE_SERVICE_UUID       "56454c58-494f-0000-0000-000000000001"
#define BLE_CHAR_FLASHING_UUID "56454c58-494f-0000-0000-000000000002"
#define BLE_CHAR_SERIAL_UUID   "56454c58-494f-0000-0000-000000000003"

/**
 * @brief Callback for incoming data on the Flashing characteristic.
 * @param data  Pointer to received payload bytes
 * @param len   Number of bytes received
 */
typedef void (*ble_data_cb_t)(uint8_t *data, size_t len);

/**
 * @brief Callback for incoming data on the Serial characteristic (Write Without Response).
 */
typedef void (*ble_serial_cb_t)(uint8_t *data, size_t len);

/**
 * @brief Initialize NimBLE stack, register GATT services, start advertising.
 */
void ble_service_init(void);

/**
 * @brief Register callback for Flashing characteristic write events.
 */
void ble_service_set_flashing_callback(ble_data_cb_t cb);

/**
 * @brief Register callback for Serial characteristic write events.
 * Receives raw bytes from Webapp → forwarded to Arduino via USB CDC.
 */
void ble_service_set_serial_callback(ble_serial_cb_t cb);

/**
 * @brief Send a BLE Notification on the Flashing characteristic.
 * Used to send ACK/ERR responses back to the Webapp.
 */
void ble_service_send_notify_flashing(uint8_t *data, size_t len);

/**
 * @brief Send a BLE Notification on the Serial characteristic.
 * Used to forward Arduino serial output to the Webapp.
 */
void ble_service_send_notify_serial(uint8_t *data, size_t len);

/**
 * @brief Check if a BLE central is currently connected.
 * @return true if connected
 */
bool ble_service_is_connected(void);
