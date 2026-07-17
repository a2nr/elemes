#include "device_name.h"
#include <string.h>
#include <stdio.h>
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_mac.h"
#include "esp_log.h"

static const char *TAG = "DEV_NAME";
static char s_device_name[VELXIO_NAME_MAX_LEN] = {0};
static bool s_is_custom = false;

static void generate_mac_suffix_name(void)
{
    uint8_t mac[6];
    esp_err_t mac_err = esp_read_mac(mac, ESP_MAC_BT);
    if (mac_err != ESP_OK) {
        ESP_LOGW(TAG, "esp_read_mac failed (%d), using fallback suffix", mac_err);
        snprintf(s_device_name, sizeof(s_device_name),
                 "Velxio-0000");
    } else {
        snprintf(s_device_name, sizeof(s_device_name),
                 "Velxio-%02X%02X", mac[4], mac[5]);
    }
    s_is_custom = false;
    ESP_LOGI(TAG, "Generated device name from MAC: %s", s_device_name);
}

void device_name_init(void)
{
    nvs_handle_t h;
    esp_err_t err = nvs_open(VELXIO_NVS_NAMESPACE, NVS_READONLY, &h);
    if (err == ESP_OK) {
        size_t len = sizeof(s_device_name);
        err = nvs_get_str(h, VELXIO_NVS_KEY_NAME, s_device_name, &len);
        nvs_close(h);
        if (err == ESP_OK && strlen(s_device_name) > 0) {
            s_is_custom = true;
            ESP_LOGI(TAG, "Loaded custom device name from NVS: %s", s_device_name);
            return;
        }
        ESP_LOGI(TAG, "NVS open OK but no custom name key, using MAC suffix");
    } else {
        ESP_LOGI(TAG, "NVS namespace 'velxio' not found (err=%d), using MAC suffix", err);
    }
    generate_mac_suffix_name();
}

const char *device_name_get(void)
{
    return s_device_name;
}

bool device_name_is_custom(void)
{
    return s_is_custom;
}

esp_err_t device_name_set_custom(const char *name)
{
    if (!name || strlen(name) == 0) {
        return ESP_ERR_INVALID_ARG;
    }

    size_t prefix = (strncmp(name, "Velxio-", 7) == 0) ? 0 : 7;
    if (strlen(name) + prefix >= VELXIO_NAME_MAX_LEN) {
        ESP_LOGE(TAG, "Name too long (max %d chars including prefix)", VELXIO_NAME_MAX_LEN - 1);
        return ESP_ERR_INVALID_SIZE;
    }

    char full_name[VELXIO_NAME_MAX_LEN];
    if (prefix == 0) {
        snprintf(full_name, sizeof(full_name), "%s", name);
    } else {
        snprintf(full_name, sizeof(full_name), "Velxio-%s", name);
    }

    nvs_handle_t h;
    esp_err_t err = nvs_open(VELXIO_NVS_NAMESPACE, NVS_READWRITE, &h);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS open failed: %d", err);
        return err;
    }

    err = nvs_set_str(h, VELXIO_NVS_KEY_NAME, full_name);
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);

    if (err == ESP_OK) {
        ESP_LOGI(TAG, "Saved custom device name: %s", full_name);
        snprintf(s_device_name, sizeof(s_device_name), "%s", full_name);
        s_is_custom = true;
    } else {
        ESP_LOGE(TAG, "NVS save failed: %d", err);
    }
    return err;
}

void device_name_get_ap_ssid(char *buf, size_t buf_len)
{
    const char *name = s_device_name;
    size_t len = strlen(name);
    const char *suffix = (len >= 4) ? (name + len - 4) : "0000";
    snprintf(buf, buf_len, "Velxio-Setup-%s", suffix);
}
