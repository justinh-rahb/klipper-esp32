// ESP32-C3 Klipper console using direct UART or USB Serial/JTAG drivers.
// Direct driver access keeps ESP-IDF VFS and line-ending translation away
// from Klipper's binary framing.
//
// Copyright (C) 2024 Nikhil Robinson <nikhil@techprogeny.com>
// Panda Breath safety adaptation: project contributors
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include <string.h>

#include "autoconf.h"
#include "board/internal.h"
#include "board/serial_irq.h"
#include "command.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sched.h"

#if defined(CONFIG_KLIPPER_CONSOLE_UART)
#include "driver/uart.h"
#elif defined(CONFIG_KLIPPER_CONSOLE_USB_CDC)
#include "driver/usb_serial_jtag.h"
#endif

#ifndef CONFIG_KLIPPER_CONSOLE_RX_BUFFER_SIZE
#define CONFIG_KLIPPER_CONSOLE_RX_BUFFER_SIZE 4096
#endif

#ifndef CONFIG_KLIPPER_UART_TX_BUFFER_SIZE
#define CONFIG_KLIPPER_UART_TX_BUFFER_SIZE 256
#endif

static volatile uint8_t console_active;
static volatile uint8_t tx_pending;

// Compatibility stubs retained for board/internal.h users.
void report_errno(char *where, int rc) { (void)where; (void)rc; }
int set_non_blocking(int fd) { (void)fd; return 0; }
int set_close_on_exec(int fd) { (void)fd; return 0; }

static int
console_read(uint8_t *buf, int maxlen)
{
#if defined(CONFIG_KLIPPER_CONSOLE_UART)
    return uart_read_bytes(CONFIG_KLIPPER_UART_NUM, buf, maxlen, 0);
#elif defined(CONFIG_KLIPPER_CONSOLE_USB_CDC)
    return usb_serial_jtag_read_bytes(buf, maxlen, 0);
#else
    (void)buf;
    (void)maxlen;
    return 0;
#endif
}

static int
console_write_all(const uint8_t *buf, int len)
{
    int sent = 0;
    while (sent < len) {
        int ret;
#if defined(CONFIG_KLIPPER_CONSOLE_UART)
        ret = uart_write_bytes(CONFIG_KLIPPER_UART_NUM, buf + sent,
                               len - sent);
#elif defined(CONFIG_KLIPPER_CONSOLE_USB_CDC)
        ret = usb_serial_jtag_write_bytes(buf + sent, len - sent,
                                         pdMS_TO_TICKS(10));
#else
        return 0;
#endif
        if (ret <= 0)
            return sent ? sent : ret;
        sent += ret;
    }
    return sent;
}

int
console_setup(char *name)
{
    (void)name;

#if defined(CONFIG_KLIPPER_CONSOLE_UART)
    uart_config_t cfg = {
        .baud_rate = CONFIG_KLIPPER_UART_BAUD_RATE,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_APB,
    };
    ESP_ERROR_CHECK(uart_driver_install(
        CONFIG_KLIPPER_UART_NUM, CONFIG_KLIPPER_UART_RX_BUFFER_SIZE,
        CONFIG_KLIPPER_UART_TX_BUFFER_SIZE, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(CONFIG_KLIPPER_UART_NUM, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(
        CONFIG_KLIPPER_UART_NUM, CONFIG_KLIPPER_UART_TX_PIN,
        CONFIG_KLIPPER_UART_RX_PIN, CONFIG_KLIPPER_UART_RTS_PIN,
        CONFIG_KLIPPER_UART_CTS_PIN));
#elif defined(CONFIG_KLIPPER_CONSOLE_USB_CDC)
    usb_serial_jtag_driver_config_t cfg = {
        .rx_buffer_size = CONFIG_KLIPPER_CONSOLE_RX_BUFFER_SIZE,
        .tx_buffer_size = CONFIG_KLIPPER_UART_TX_BUFFER_SIZE,
    };
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&cfg));
#else
#error "A Klipper console transport must be selected"
#endif

    console_active = 1;
    tx_pending = 0;
    return 0;
}

void
serial_enable_tx_irq(void)
{
    tx_pending = 1;
    sched_wake_tasks();
}

void
console_io_task(void)
{
    if (!console_active)
        return;

    uint8_t rxbuf[CONFIG_KLIPPER_CONSOLE_RX_BUFFER_SIZE];
    int count = console_read(rxbuf, sizeof(rxbuf));
    for (int i = 0; i < count; i++)
        serial_rx_byte(rxbuf[i]);

    if (!tx_pending)
        return;

    tx_pending = 0;
    uint8_t txbuf[MESSAGE_MAX];
    int len = 0;
    uint8_t byte;
    while (len < (int)sizeof(txbuf) && serial_get_tx_byte(&byte) >= 0)
        txbuf[len++] = byte;
    if (len)
        console_write_all(txbuf, len);
    if (len == (int)sizeof(txbuf)) {
        // The generic transmit buffer may contain another packet. A harmless
        // extra pass is preferable to consuming a byte merely to probe it.
        tx_pending = 1;
        sched_wake_tasks();
    }
}
DECL_TASK(console_io_task);

void
console_shutdown(void)
{
    // Keep transport alive so the host can retrieve the shutdown reason and
    // issue config_reset. Klipper itself rejects non-shutdown commands.
}
DECL_SHUTDOWN(console_shutdown);

void
console_sleep(void)
{
    if (!console_active)
        vTaskDelay(pdMS_TO_TICKS(100));
}
