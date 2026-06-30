#include "esp_log.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "led_button.h"

static const char *TAG = "LED_BTN";

static led_pattern_t current_pattern = LED_OFF;
static bool button_previous_state = true;
static bool button_pressed_flag = false;
static int64_t last_toggle_time = 0;
static bool blink_state = false;

static void set_led(bool red, bool green, bool blue)
{
    gpio_set_level(LED_GPIO_RED, red ? 1 : 0);
    gpio_set_level(LED_GPIO_GREEN, green ? 1 : 0);
    gpio_set_level(LED_GPIO_BLUE, blue ? 1 : 0);
}

void led_button_init(void)
{
    gpio_set_direction(LED_GPIO_RED, GPIO_MODE_OUTPUT);
    gpio_set_direction(LED_GPIO_GREEN, GPIO_MODE_OUTPUT);
    gpio_set_direction(LED_GPIO_BLUE, GPIO_MODE_OUTPUT);

    gpio_set_direction(BTN_GPIO_RETRY, GPIO_MODE_INPUT);
    gpio_set_pull_mode(BTN_GPIO_RETRY, GPIO_PULLUP_ONLY);

    set_led(false, false, false);
    button_previous_state = gpio_get_level(BTN_GPIO_RETRY);
    ESP_LOGI(TAG, "LED + Button initialized");
}

void led_set_pattern(led_pattern_t pattern)
{
    current_pattern = pattern;

    switch (pattern) {
    case LED_OFF:
        set_led(false, false, false);
        break;
    case LED_GREEN:
        set_led(false, true, false);
        break;
    case LED_RED:
        set_led(true, false, false);
        break;
    case LED_BLUE:
        set_led(false, false, true);
        break;
    case LED_GREEN_BLINK:
    case LED_RED_BLINK:
    case LED_BLUE_BLINK:
        /* Toggle handled by led_button_tick(). Start off. */
        blink_state = false;
        last_toggle_time = esp_timer_get_time() / 1000;
        set_led(false, false, false);
        break;
    }
}

bool button_retry_pressed(void)
{
    bool current = gpio_get_level(BTN_GPIO_RETRY);

    if (button_previous_state && !current) {
        button_previous_state = current;
        ESP_LOGI(TAG, "Retry button pressed");
        return true;
    }

    button_previous_state = current;
    return false;
}

void led_button_tick(void)
{
    if (current_pattern != LED_GREEN_BLINK &&
        current_pattern != LED_RED_BLINK &&
        current_pattern != LED_BLUE_BLINK) {
        return;
    }

    int64_t now = esp_timer_get_time() / 1000;
    int64_t interval = (current_pattern == LED_RED_BLINK) ? 100 : 200;

    if (now - last_toggle_time >= interval) {
        last_toggle_time = now;
        blink_state = !blink_state;

        switch (current_pattern) {
        case LED_BLUE_BLINK:
            set_led(false, false, blink_state);
            break;
        case LED_RED_BLINK:
            set_led(blink_state, false, false);
            break;
        case LED_GREEN_BLINK:
            set_led(false, blink_state, false);
            break;
        default:
            break;
        }
    }
}
