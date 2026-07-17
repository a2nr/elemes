#pragma once
#include <stdbool.h>

/**
 * Start WiFi SoftAP + HTTP config server.
 * Blocks forever (does not return).
 * AP SSID: "Velxio-Setup-XXXX" (MAC suffix)
 * AP Password: "velxio123"
 * Config page: http://192.168.4.1
 */
void wifi_ap_start_and_block(void) __attribute__((noreturn));
