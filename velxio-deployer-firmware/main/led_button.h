/**
 * @file led_button.h
 * @brief Status LED (RGB) and tactile Retry button.
 *
 * LED patterns:
 *   BLUE_BLINK — advertising / receiving data
 *   BLUE       — verification in progress
 *   GREEN      — flash succeeded, serial bridge active
 *   RED        — STK500 target error
 *   RED_BLINK  — checksum mismatch
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

#define LED_GPIO_RED    13
#define LED_GPIO_GREEN  12
#define LED_GPIO_BLUE   14
#define BTN_GPIO_RETRY  0   /**< GPIO0 (BOOT button on most dev boards) */

/** LED visual patterns. */
typedef enum {
    LED_OFF,               /**< All off */
    LED_GREEN,             /**< Solid green — success / serial bridge */
    LED_RED,               /**< Solid red — target error */
    LED_BLUE,              /**< Solid blue — verification in progress */
    LED_GREEN_BLINK,       /**< Blinking green */
    LED_RED_BLINK,         /**< Fast blinking red — checksum error (100ms) */
    LED_BLUE_BLINK,        /**< Medium blinking blue — receiving chunks (200ms) */
    LED_BLUE_BLINK_SLOW,   /**< Slow blinking blue — idle / advertising (1000ms) */
    LED_BLUE_BLINK_FAST    /**< Fast blinking blue — flashing in progress (100ms) */
} led_pattern_t;

void led_button_init(void);

/**
 * @brief Set the LED visual pattern.
 * @param pattern  Pattern from led_pattern_t enum
 */
void led_set_pattern(led_pattern_t pattern);

/**
 * @brief Check if the Retry button was just pressed (edge-triggered).
 * @return true on falling edge detection
 */
bool button_retry_pressed(void);

/**
 * @brief Periodic tick for LED blink patterns. Call from main loop (~10ms).
 */
void led_button_tick(void);
