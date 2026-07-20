/**
 * @file usb_host.h
 * @brief USB Host CDC driver using CherryUSB.
 *
 * Manages enumeration of Arduino Uno/Nano as a CDC serial device,
 * providing read/write access for STK500v1 flashing and serial bridge.
 *
 * RX routing: by default the rx_task feeds the serial-bridge callback.
 * During flashing, usb_host_rx_claim() suspends the rx/monitor tasks so
 * STK500v1 can read CDC responses exclusively via usb_host_read_cdc().
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

/**
 * @brief Callback invoked when data is received from Arduino via USB CDC
 *        while RX is NOT claimed (serial bridge mode).
 * @param data  Received bytes
 * @param len   Number of bytes
 */
typedef void (*usb_data_cb_t)(uint8_t *data, size_t len);

/**
 * @brief Initialise CherryUSB Host driver and start monitor/rx tasks.
 * @return true on success
 */
bool usb_host_init(void);

/**
 * @brief Check if an Arduino CDC device is currently enumerated.
 * @return true if connected
 */
bool usb_host_arduino_connected(void);

/**
 * @brief Write data to the Arduino via USB CDC (blocking until TX done).
 * @return true if write succeeded
 */
bool usb_host_write_cdc(const uint8_t *data, size_t len);

/**
 * @brief Read up to len bytes from Arduino CDC within timeout.
 *
 * Only valid while RX is claimed (i.e. during flashing). Reads from the
 * CherryUSB ringbuffer; blocks up to timeout_ms waiting for data.
 *
 * @param buf        Destination buffer
 * @param len        Max bytes to read
 * @param timeout_ms Max wait time
 * @return number of bytes read (>=0), or negative on error/timeout
 */
int usb_host_read_cdc(uint8_t *buf, size_t len, uint32_t timeout_ms);

/**
 * @brief Drain up to N stale bytes from CDC ringbuffer with short timeout.
 *
 * Reads and discards bytes left in the CherryUSB ringbuffer from a prior
 * serial bridge session. Returns number of bytes drained.
 *
 * @param max_bytes Maximum bytes to drain
 * @param total_ms  Total time budget for draining
 * @return number of bytes drained
 */
size_t usb_host_drain_cdc(size_t max_bytes, uint32_t total_ms);

/**
 * @brief Register callback for incoming CDC serial data (serial bridge).
 */
void usb_host_set_serial_callback(usb_data_cb_t cb);

/**
 * @brief Claim USB CDC RX for STK500v1 flashing.
 *
 * Suspends the rx_task and monitor_task so STK500v1 can exclusively read
 * responses via usb_host_read_cdc(). Reconfigures the CDC port with a
 * bounded rx_timeout so reads actually return on timeout.
 */
void usb_host_rx_claim(void);

/**
 * @brief Release USB CDC RX back to serial bridge mode.
 *
 * Resumes rx_task and monitor_task and restores rx_timeout=0 (blocking).
 */
void usb_host_rx_release(void);

/**
 * @brief Pulse DTR low then high to reset Arduino into optiboot.
 *
 * Mirrors avrdude's Arduino autoreset: DTR/RTS low ~1ms, then high,
 * wait 50ms for optiboot to enter. Idempotent if no device present.
 */
void usb_host_reset_arduino(void);

/**
 * @brief Set the serial bridge baud rate for USB CDC communication.
 *
 * Reconfigures the CDC termios immediately if the serial device is active
 * and RX is not claimed (i.e. in serial bridge mode). If RX is claimed
 * (STK500 flashing), stores the baud and applies it on rx_release().
 *
 * Safe to call from any context (stores value, configures if possible).
 * @param baud  Baud rate (e.g. 9600, 19200, 38400)
 */
void usb_host_set_baud_rate(uint32_t baud);

/**
 * @brief Deinitialise USB Host and release resources.
 */
void usb_host_deinit(void);
