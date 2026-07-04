#include <string.h>
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_nimble_hci.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "host/ble_hs_id.h"
#include "host/ble_uuid.h"
#include "host/ble_gap.h"
#include "host/util/util.h"
#include "host/ble_sm.h"
#include "host/ble_att.h"

void ble_store_config_init(void);
#include "services/gap/ble_svc_gap.h"
#include "state_machine.h"
#include "services/gatt/ble_svc_gatt.h"
#include "ble_service.h"
#include "serial_bridge.h"
#include "state_machine.h"
#include "binary_parser.h"
#include "usb_host.h"

static const char *TAG = "BLE_SVC";

static ble_data_cb_t flashing_callback = NULL;
static ble_serial_cb_t serial_callback = NULL;
static uint16_t flashing_attr_handle;
static uint16_t serial_attr_handle;
static bool ble_connected = false;
static uint16_t conn_handle = 0;
static uint8_t own_addr_type = 0;

static const ble_uuid128_t service_uuid = BLE_UUID128_INIT(
    0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x4F, 0x49, 0x58, 0x4C, 0x45, 0x56
);

static const ble_uuid128_t flashing_char_uuid = BLE_UUID128_INIT(
    0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x4F, 0x49, 0x58, 0x4C, 0x45, 0x56
);

static const ble_uuid128_t serial_char_uuid = BLE_UUID128_INIT(
    0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x4F, 0x49, 0x58, 0x4C, 0x45, 0x56
);

static int ble_gap_event_cb(struct ble_gap_event *event, void *arg);

static int flashing_char_access_cb(uint16_t conn_handle, uint16_t attr_handle,
                                    struct ble_gatt_access_ctxt *ctxt, void *arg)
{
    if (ctxt->op == BLE_GATT_ACCESS_OP_READ_CHR) {
        /* Return current state machine state as 1 byte.
         * Webapp polls this after END to detect flash completion:
         *   0=IDLE, 1=RECEIVING, 2=VERIFYING, 3=FLASHING,
         *   4=SERIAL_BRIDGE (success), 5=ERROR_TARGET, 6=ERROR_CHECKSUM */
        uint8_t state = (uint8_t)state_machine_get_current();
        os_mbuf_append(ctxt->om, &state, 1);
        ESP_LOGD(TAG, "Flashing read: state=%d (%s)",
                 state, state_machine_get_state_name());
        return 0;
    }

    if (ctxt->op == BLE_GATT_ACCESS_OP_WRITE_CHR) {
        size_t len = OS_MBUF_PKTLEN(ctxt->om);
        uint8_t *data = malloc(len);
        if (data) {
            os_mbuf_copydata(ctxt->om, 0, len, data);
            ESP_LOGI(TAG, "Flashing write: len=%d conn=%d handle=0x%04X cmd=0x%02X",
                     len, conn_handle, attr_handle, len > 0 ? data[0] : 0);
            if (flashing_callback) {
                flashing_callback(data, len);
            }
            free(data);
        }
    }
    return 0;
}

static int serial_char_access_cb(uint16_t conn_handle, uint16_t attr_handle,
                                    struct ble_gatt_access_ctxt *ctxt, void *arg)
{
    if (ctxt->op == BLE_GATT_ACCESS_OP_WRITE_CHR) {
        size_t len = OS_MBUF_PKTLEN(ctxt->om);
        uint8_t *data = malloc(len);
        if (data) {
            os_mbuf_copydata(ctxt->om, 0, len, data);
            ESP_LOGI(TAG, "Serial write: len=%d conn=%d", len, conn_handle);

            if (len == 5 && data[0] == CMD_SET_BAUD) {
                uint32_t baud = (uint32_t)data[1] | ((uint32_t)data[2] << 8) |
                                ((uint32_t)data[3] << 16) | ((uint32_t)data[4] << 24);
                ESP_LOGI(TAG, "CMD_SET_BAUD: %lu", (unsigned long)baud);
                usb_host_set_baud_rate(baud);
            } else {
                serial_bridge_on_ble_write(data, len);
            }
            free(data);
        }
    }
    return 0;
}

static const struct ble_gatt_svc_def gatt_svcs[] = {
    {
        .type = BLE_GATT_SVC_TYPE_PRIMARY,
        .uuid = &service_uuid.u,
        .characteristics = (struct ble_gatt_chr_def[]) {
            {
                .uuid = &flashing_char_uuid.u,
                .access_cb = flashing_char_access_cb,
                .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE | BLE_GATT_CHR_F_NOTIFY,
                .val_handle = &flashing_attr_handle
            },
            {
                .uuid = &serial_char_uuid.u,
                .access_cb = serial_char_access_cb,
                .flags = BLE_GATT_CHR_F_WRITE_NO_RSP | BLE_GATT_CHR_F_NOTIFY,
                .val_handle = &serial_attr_handle
            },
            {
                0
            }
        }
    },
    {
        0
    }
};

static void ble_restart_adv(void)
{
    int rc;
    struct ble_gap_adv_params adv_params;
    uint8_t adv_data[31];
    uint8_t adv_data_len = 0;

    struct ble_hs_adv_fields fields;
    memset(&fields, 0, sizeof(fields));
    fields.flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;
    fields.name = (uint8_t *)"Velxio";
    fields.name_len = 6;
    fields.name_is_complete = 0;
    fields.uuids16 = NULL;
    fields.num_uuids16 = 0;

    rc = ble_hs_adv_set_fields(&fields, adv_data, &adv_data_len, sizeof(adv_data));
    if (rc != 0) {
        ESP_LOGE(TAG, "ble_hs_adv_set_fields rc=%d", rc);
        return;
    }

    rc = ble_gap_adv_set_data(adv_data, adv_data_len);
    if (rc != 0) {
        ESP_LOGE(TAG, "ble_gap_adv_set_data rc=%d", rc);
        return;
    }

    memset(&adv_params, 0, sizeof(adv_params));
    adv_params.conn_mode = BLE_GAP_CONN_MODE_UND;
    adv_params.disc_mode = BLE_GAP_DISC_MODE_GEN;

    rc = ble_gap_adv_start(own_addr_type, NULL, BLE_HS_FOREVER,
                           &adv_params, ble_gap_event_cb, NULL);
    if (rc == 0) {
        ESP_LOGI(TAG, "BLE advertising started");
    } else {
        ESP_LOGE(TAG, "ble_gap_adv_start rc=%d", rc);
    }
}

static int ble_gap_event_cb(struct ble_gap_event *event, void *arg)
{
    switch (event->type) {
    case BLE_GAP_EVENT_CONNECT:
        conn_handle = event->connect.conn_handle;
        ble_connected = true;
        ESP_LOGI(TAG, "BLE connected, handle=%d", conn_handle);
        break;

    case BLE_GAP_EVENT_DISCONNECT:
        conn_handle = 0;
        ble_connected = false;
        ESP_LOGI(TAG, "BLE disconnected");
        state_machine_process_event(EVENT_BLE_DISCONNECT, NULL);
        ble_restart_adv();
        break;

    case BLE_GAP_EVENT_ADV_COMPLETE:
        ESP_LOGI(TAG, "ADV_COMPLETE, reason=%d", event->adv_complete.reason);
        ble_restart_adv();
        break;

    case BLE_GAP_EVENT_SUBSCRIBE:
        ESP_LOGI(TAG, "Subscribe attr_handle=%d notify=%d indicate=%d prev_notify=%d prev_indicate=%d",
                 event->subscribe.attr_handle,
                 event->subscribe.cur_notify,
                 event->subscribe.cur_indicate,
                 event->subscribe.prev_notify,
                 event->subscribe.prev_indicate);
        break;

    default:
        break;
    }
    return 0;
}

static void ble_on_reset(int reason)
{
    ESP_LOGE(TAG, "NimBLE host reset, reason=%d", reason);
}

static void ble_on_sync(void)
{
    int rc;

    rc = ble_hs_util_ensure_addr(1);
    if (rc != 0) {
        ESP_LOGE(TAG, "ble_hs_util_ensure_addr failed: %d", rc);
        return;
    }

    rc = ble_hs_id_infer_auto(0, &own_addr_type);
    if (rc != 0) {
        ESP_LOGE(TAG, "ble_hs_id_infer_auto failed: %d", rc);
        return;
    }

    ESP_LOGI(TAG, "Address type: %d", own_addr_type);

    rc = ble_att_set_preferred_mtu(255);
    if (rc == 0) {
        ESP_LOGI(TAG, "Preferred MTU set: 255");
    } else {
        ESP_LOGW(TAG, "ble_att_set_preferred_mtu failed: %d", rc);
    }

    ble_restart_adv();
}

static void host_task(void *param)
{
    nimble_port_run();
}

void ble_service_init(void)
{
    esp_nimble_hci_init();
    nimble_port_init();

    ble_hs_cfg.reset_cb = ble_on_reset;
    ble_hs_cfg.sync_cb = ble_on_sync;
    ble_hs_cfg.sm_io_cap = BLE_HS_IO_NO_INPUT_OUTPUT;
    ble_hs_cfg.sm_sc = 0;

    ble_svc_gap_init();
    ble_svc_gatt_init();

    ble_gatts_count_cfg(gatt_svcs);
    ble_gatts_add_svcs(gatt_svcs);

    ble_svc_gap_device_name_set("Velxio-Deployer");
    ble_svc_gap_device_appearance_set(0x0080);

    ble_store_config_init();

    nimble_port_freertos_init(host_task);
    ESP_LOGI(TAG, "BLE service initialized");
}

void ble_service_set_flashing_callback(ble_data_cb_t cb)
{
    flashing_callback = cb;
}

void ble_service_set_serial_callback(ble_serial_cb_t cb)
{
    serial_callback = cb;
}

void ble_service_send_notify_flashing(uint8_t *data, size_t len)
{
    if (!ble_connected) return;

    struct os_mbuf *om = NULL;
    for (int retry = 0; retry < 3; retry++) {
        om = ble_hs_mbuf_from_flat(data, len);
        if (om) break;
        ESP_LOGW(TAG, "flashing mbuf alloc failed (retry %d/3)", retry + 1);
        vTaskDelay(1);
    }

    if (!om) {
        ESP_LOGE(TAG, "flashing ACK DROPPED: mbuf pool exhausted after 3 retries");
        return;
    }

    int rc = ble_gatts_notify_custom(conn_handle, flashing_attr_handle, om);
    if (rc != 0) {
        ESP_LOGW(TAG, "flashing notify failed: rc=%d handle=0x%04X conn=%d",
                 rc, flashing_attr_handle, conn_handle);
    }
}

void ble_service_send_notify_serial(uint8_t *data, size_t len)
{
    if (!ble_connected) return;
    struct os_mbuf *om = ble_hs_mbuf_from_flat(data, len);
    if (om) {
        int rc = ble_gatts_notify_custom(conn_handle, serial_attr_handle, om);
        if (rc != 0) {
            ESP_LOGW(TAG, "serial notify failed: rc=%d handle=0x%04X conn=%d",
                     rc, serial_attr_handle, conn_handle);
        }
    }
}

bool ble_service_is_connected(void)
{
    return ble_connected;
}
