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
    LED_OFF,           /**< All off */
    LED_GREEN,         /**< Solid green — success */
    LED_RED,           /**< Solid red — error */
    LED_BLUE,          /**< Solid blue — busy */
    LED_GREEN_BLINK,   /**< Blinking green */
    LED_RED_BLINK,     /**< Blinking red — checksum error */
    LED_BLUE_BLINK     /**< Blinking blue — advertising/receiving */
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
