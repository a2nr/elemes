#include "wifi_ap.h"
#include "device_name.h"
#include <string.h>
#include <stdio.h>
#include <ctype.h>
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_http_server.h"
#include "nvs_flash.h"
#include "esp_system.h"

static const char *TAG = "WIFI_AP";

/* Embedded config_page.html — linked via EMBED_TXTFILES in CMakeLists.txt */
extern const uint8_t config_page_html_start[] asm("_binary_config_page_html_start");
extern const uint8_t config_page_html_end[]   asm("_binary_config_page_html_end");

#define AP_PASSWORD "velxio123"

/* ---------- Minimal JSON helpers ---------- */

/**
 * @brief Extract string value for a given key from a flat JSON object.
 *
 * Parses  {"key":"value"}  — no nesting, no escaping support.
 * Returns pointer to the value text (null-terminated in-place) or NULL.
 */
static const char *json_get_string(const char *json, const char *key)
{
    if (!json || !key) return NULL;

    /* Build search pattern: "key":" */
    char pattern[64];
    int n = snprintf(pattern, sizeof(pattern), "\"%s\":\"", key);
    if (n < 0 || (size_t)n >= sizeof(pattern)) return NULL;

    const char *p = strstr(json, pattern);
    if (!p) return NULL;

    p += strlen(pattern);  /* point to first char of value */
    /* Find closing quote */
    const char *end = strchr(p, '"');
    if (!end) return NULL;

    /* Return the value as a mutable string (caller gets const, but we
       write a null to mark the end — safe since json is in a writable buf) */
    /* Cast away const: the caller owns a writable buffer */
    char *mutable = (char *)end;
    *mutable = '\0';
    return p;
}

/* ---------- HTTP handlers ---------- */

static esp_err_t get_root_handler(httpd_req_t *req)
{
    const size_t html_len = config_page_html_end - config_page_html_start;
    ESP_LOGI(TAG, "Serving config page (%zu bytes)", html_len);
    httpd_resp_set_type(req, "text/html");
    httpd_resp_send(req, (const char *)config_page_html_start, html_len);
    return ESP_OK;
}

static esp_err_t get_name_handler(httpd_req_t *req)
{
    const char *name = device_name_get();
    char resp[128];
    snprintf(resp, sizeof(resp), "{\"name\":\"%s\"}", name);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, resp, strlen(resp));
    return ESP_OK;
}

/**
 * Validate suffix: only alphanumeric, dash, and underscore allowed.
 */
static bool is_valid_suffix(const char *s)
{
    if (!s || *s == '\0') return false;
    for (; *s; s++) {
        if (!isalnum((unsigned char)*s) && *s != '-' && *s != '_')
            return false;
    }
    return true;
}

static esp_err_t post_name_handler(httpd_req_t *req)
{
    char buf[256];
    int remaining = req->content_len;

    if (remaining >= (int)sizeof(buf)) {
        httpd_resp_set_type(req, "application/json");
        httpd_resp_sendstr(req, "{\"success\":false,\"error\":\"Payload too large\"}");
        return ESP_OK;
    }

    int ret = httpd_req_recv(req, buf, remaining);
    if (ret <= 0) {
        httpd_resp_set_type(req, "application/json");
        httpd_resp_sendstr(req, "{\"success\":false,\"error\":\"Failed to read body\"}");
        return ESP_OK;
    }
    buf[ret] = '\0';

    /* Parse JSON: {"name":"Velxio-XXXX"} */
    const char *name_val = json_get_string(buf, "name");
    if (!name_val) {
        httpd_resp_set_type(req, "application/json");
        httpd_resp_sendstr(req, "{\"success\":false,\"error\":\"Missing 'name' field\"}");
        return ESP_OK;
    }

    const char *full_name = name_val;

    /* Extract suffix after "Velxio-" prefix */
    const char *suffix = full_name;
    if (strncmp(full_name, "Velxio-", 7) == 0) {
        suffix = full_name + 7;
    }

    if (!is_valid_suffix(suffix)) {
        httpd_resp_set_type(req, "application/json");
        httpd_resp_sendstr(req,
            "{\"success\":false,\"error\":\"Only alphanumeric, dash, underscore allowed\"}");
        return ESP_OK;
    }

    esp_err_t err = device_name_set_custom(full_name);

    if (err != ESP_OK) {
        httpd_resp_set_type(req, "application/json");
        httpd_resp_sendstr(req, "{\"success\":false,\"error\":\"NVS write failed\"}");
        return ESP_OK;
    }

    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr(req, "{\"success\":true}");

    ESP_LOGI(TAG, "Name saved, rebooting in 1 second...");
    vTaskDelay(pdMS_TO_TICKS(1000));
    esp_restart();

    /* Never reached */
    return ESP_OK;
}

/* ---------- Public API ---------- */

void wifi_ap_start_and_block(void)
{
    ESP_LOGI(TAG, "Starting WiFi SoftAP + HTTP config server...");

    /* Initialise network interface and event loop */
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_ap();

    /* Initialise WiFi in AP mode */
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    /* Build AP SSID from device MAC */
    char ap_ssid[32] = {0};
    device_name_get_ap_ssid(ap_ssid, sizeof(ap_ssid));

    /* Configure SoftAP */
    wifi_config_t wifi_config = {
        .ap = {
            .ssid_len        = 0,
            .max_connection   = 4,
            .authmode         = WIFI_AUTH_WPA_WPA2_PSK,
        },
    };
    snprintf((char *)wifi_config.ap.ssid,    sizeof(wifi_config.ap.ssid),    "%s", ap_ssid);
    snprintf((char *)wifi_config.ap.password, sizeof(wifi_config.ap.password), "%s", AP_PASSWORD);

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "SoftAP started — SSID: %s, Password: %s", ap_ssid, AP_PASSWORD);

    /* Start HTTP config server */
    httpd_handle_t server = NULL;
    httpd_config_t httpd_conf = HTTPD_DEFAULT_CONFIG();

    if (httpd_start(&server, &httpd_conf) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start HTTP server");
        while (1) {
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }

    /* Register URI handlers */
    httpd_uri_t uri_get_root = {
        .uri       = "/",
        .method    = HTTP_GET,
        .handler   = get_root_handler,
        .user_ctx  = NULL,
    };
    httpd_register_uri_handler(server, &uri_get_root);

    httpd_uri_t uri_get_name = {
        .uri       = "/api/name",
        .method    = HTTP_GET,
        .handler   = get_name_handler,
        .user_ctx  = NULL,
    };
    httpd_register_uri_handler(server, &uri_get_name);

    httpd_uri_t uri_post_name = {
        .uri       = "/api/name",
        .method    = HTTP_POST,
        .handler   = post_name_handler,
        .user_ctx  = NULL,
    };
    httpd_register_uri_handler(server, &uri_post_name);

    ESP_LOGI(TAG, "HTTP config server running at http://192.168.4.1");

    /* Block forever — this function never returns */
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
