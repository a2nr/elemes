/**
 * @file serial_bridge.h
 * @brief Transparent bridge: USB CDC <-> BLE Serial characteristic.
 *
 * When active, data from Arduino's Serial.print() is read via USB Host
 * and immediately forwarded as BLE Notify on the Serial characteristic.
 * Data from the Webapp (BLE Write) is forwarded to Arduino via USB CDC.
 *
 * Throttled to prevent BLE congestion (max 20 packets/sec).
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

void serial_bridge_init(void);

/**
 * @brief Start bridging between USB CDC and BLE Serial.
 */
void serial_bridge_start(void);

/**
 * @brief Stop bridging and release BLE Serial notifications.
 */
void serial_bridge_stop(void);

/**
 * @brief Check if bridge is currently active.
 * @return true if active
 */
bool serial_bridge_is_active(void);

/**
 * @brief Periodic tick for throttling and buffer management.
 */
void serial_bridge_tick(void);

/**
 * @brief Forward data from BLE Serial characteristic to USB CDC.
 * Called when Webapp writes to the Serial characteristic.
 * @param data  Pointer to received bytes
 * @param len   Number of bytes received
 */
void serial_bridge_on_ble_write(uint8_t *data, size_t len);

/**
 * @brief Buffer data from USB CDC (Arduino serial output).
 * Called from main's on_usb_serial_data callback. Data is buffered
 * and flushed in serial_bridge_tick() at max 20 pkt/s.
 * @param data  Pointer to received bytes
 * @param len   Number of bytes received
 */
void serial_bridge_on_usb_data(uint8_t *data, size_t len);
