#include <string.h>
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "usbh_core.h"
#include "usbh_serial.h"
#include "usb_host.h"

static const char *TAG = "USB_HOST";

static usb_data_cb_t serial_callback = NULL;
static bool arduino_connected_flag = false;
static bool initialized = false;
static bool rx_claimed = false;
static struct usbh_serial *serial_dev = NULL;
static TaskHandle_t usb_monitor_task_handle = NULL;
static TaskHandle_t usb_rx_task_handle = NULL;

/* Default termios (serial bridge): blocking RX, 115200 8N1. */
static struct usbh_serial_termios make_termios(uint32_t rx_timeout)
{
    struct usbh_serial_termios t = {
        .baudrate = 115200,
        .databits = 8,
        .parity = 0,
        .stopbits = 0,
        .rtscts = false,
        .rx_timeout = rx_timeout,
    };
    return t;
}

static void usb_rx_task(void *arg)
{
    uint8_t buf[512];
    int ret;

    while (1) {
        /* If suspended by rx_claim, just idle (suspension handled by VTaskSuspend). */
        if (serial_dev && arduino_connected_flag && !rx_claimed) {
            ret = usbh_serial_read(serial_dev, buf, sizeof(buf));
            if (ret > 0) {
                if (serial_callback) {
                    serial_callback(buf, ret);
                }
            }
        }
        vTaskDelay(1);
    }
}

static void usb_monitor_task(void *arg)
{
    struct usbh_serial *dev;

    while (1) {
        if (!arduino_connected_flag) {
            dev = usbh_serial_open("/dev/ttyACM0", USBH_SERIAL_O_RDWR);
            if (!dev) {
                dev = usbh_serial_open("/dev/ttyUSB0", USBH_SERIAL_O_RDWR);
            }
            if (dev) {
                serial_dev = dev;
                arduino_connected_flag = true;

                struct usbh_serial_termios t = make_termios(0);
                usbh_serial_control(dev, USBH_SERIAL_CMD_SET_ATTR, &t);
                /* SET_ATTR already drives DTR|RTS high internally (see
                 * usbh_serial.c SET_ATTR handler). Do NOT issue TIOCMSET
                 * with value-as-pointer — that derefs an invalid address. */

                ESP_LOGI(TAG, "Arduino connected via CherryUSB");
            }
        } else {
            int ret = usbh_serial_write(serial_dev, NULL, 0);
            if (ret < 0) {
                ESP_LOGI(TAG, "Arduino disconnected");
                arduino_connected_flag = false;
                usbh_serial_close(serial_dev);
                serial_dev = NULL;
            }
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

bool usb_host_init(void)
{
    if (initialized) return true;

    esp_err_t ret = usbh_initialize(0, ESP_USB_FS0_BASE, NULL);
    if (ret != 0) {
        ESP_LOGE(TAG, "CherryUSB init failed: %d", ret);
        return false;
    }

    xTaskCreate(usb_monitor_task, "usb_mon", 4096, NULL, 3, &usb_monitor_task_handle);
    xTaskCreate(usb_rx_task, "usb_rx", 2560, NULL, 4, &usb_rx_task_handle);

    initialized = true;
    ESP_LOGI(TAG, "USB Host initialized (CherryUSB)");
    return true;
}

bool usb_host_arduino_connected(void)
{
    return arduino_connected_flag && serial_dev != NULL;
}

bool usb_host_write_cdc(const uint8_t *data, size_t len)
{
    if (!serial_dev) return false;

    int ret = usbh_serial_write(serial_dev, data, len);
    if (ret < 0) {
        ESP_LOGE(TAG, "Serial write failed: %d", ret);
        return false;
    }
    return true;
}

int usb_host_read_cdc(uint8_t *buf, size_t len, uint32_t timeout_ms)
{
    if (!serial_dev || !arduino_connected_flag) {
        return -1;
    }
    /* CherryUSB uses serial_dev->rx_timeout_ms for the sem_take timeout
     * (see usbh_serial.c:461). Setting it inline is the documented field. */
    serial_dev->rx_timeout_ms = timeout_ms;
    int ret = usbh_serial_read(serial_dev, buf, len);
    return ret;  /* >=0 bytes, <0 on error/timeout */
}

void usb_host_set_serial_callback(usb_data_cb_t cb)
{
    serial_callback = cb;
}

void usb_host_rx_claim(void)
{
    if (!initialized || rx_claimed) return;

    /* Stop the rx/monitor tasks so they don't drain the CDC ringbuffer. */
    if (usb_rx_task_handle)      vTaskSuspend(usb_rx_task_handle);
    if (usb_monitor_task_handle) vTaskSuspend(usb_monitor_task_handle);

    if (serial_dev) {
        /* Reconfigure with bounded rx_timeout so usb_host_read_cdc returns
         * on timeout. SET_ATTR also kills+resubmits the IN URB and resets
         * the ringbuffer, clearing any stale serial data. */
        struct usbh_serial_termios t = make_termios(50);
        usbh_serial_control(serial_dev, USBH_SERIAL_CMD_SET_ATTR, &t);
    }
    rx_claimed = true;
    ESP_LOGI(TAG, "RX claimed for STK500");
}

void usb_host_rx_release(void)
{
    if (!initialized || !rx_claimed) return;

    if (serial_dev) {
        /* Restore blocking RX (rx_timeout=0 = forever) for serial bridge. */
        struct usbh_serial_termios t = make_termios(0);
        usbh_serial_control(serial_dev, USBH_SERIAL_CMD_SET_ATTR, &t);
    }
    rx_claimed = false;

    if (usb_rx_task_handle)      vTaskResume(usb_rx_task_handle);
    if (usb_monitor_task_handle) vTaskResume(usb_monitor_task_handle);
    ESP_LOGI(TAG, "RX released back to serial bridge");
}

void usb_host_reset_arduino(void)
{
    if (!serial_dev || !arduino_connected_flag) {
        ESP_LOGW(TAG, "reset_arduino: no device — skipping DTR pulse");
        return;
    }

    /* Drive DTR+RTS low to assert RESET (Arduino autoreset circuit).
     * TIOCMSET expects a pointer to uint32_t flags — NEVER pass flags
     * cast directly as the pointer (that was bug B10, a NULL+small deref). */
    uint32_t flags_low = 0;
    usbh_serial_control(serial_dev, USBH_SERIAL_CMD_TIOCMSET, &flags_low);
    vTaskDelay(pdMS_TO_TICKS(1));

    uint32_t flags_high = USBH_SERIAL_TIOCM_DTR | USBH_SERIAL_TIOCM_RTS;
    usbh_serial_control(serial_dev, USBH_SERIAL_CMD_TIOCMSET, &flags_high);
    vTaskDelay(pdMS_TO_TICKS(50));

    ESP_LOGI(TAG, "Arduino DTR pulse sent (autoreset)");
}

void usb_host_deinit(void)
{
    if (!initialized) return;

    initialized = false;
    arduino_connected_flag = false;
    rx_claimed = false;

    if (usb_monitor_task_handle) {
        vTaskDelete(usb_monitor_task_handle);
        usb_monitor_task_handle = NULL;
    }
    if (usb_rx_task_handle) {
        vTaskDelete(usb_rx_task_handle);
        usb_rx_task_handle = NULL;
    }
    if (serial_dev) {
        usbh_serial_close(serial_dev);
        serial_dev = NULL;
    }
    usbh_deinitialize(0);

    ESP_LOGI(TAG, "USB Host deinitialized");
}
