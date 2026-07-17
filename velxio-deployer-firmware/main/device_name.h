/**
 * @file device_name.h
 * @brief Device name management for Velxio firmware
 *
 * Manages persistent custom device names and MAC-address-derived
 * fallback names, stored in NVS.
 */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include "esp_err.h"

#define VELXIO_NVS_NAMESPACE "velxio"
#define VELXIO_NVS_KEY_NAME  "dev_name"
#define VELXIO_NAME_MAX_LEN  32

void device_name_init(void);
const char *device_name_get(void);
bool device_name_is_custom(void);
esp_err_t device_name_set_custom(const char *name);
void device_name_get_ap_ssid(char *buf, size_t buf_len);
