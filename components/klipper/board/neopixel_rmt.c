// Klipper NeoPixel protocol implemented with the ESP32 RMT peripheral.
//
// Copyright (C) 2026 Justin Hayes <justinh@rahb.ca>
//
// Klipper's generic bit-banger needs sub-microsecond timer ticks. The Panda
// firmware intentionally exposes a 1MHz scheduler clock, so RMT generates the
// WS2812 waveform independently at 10MHz while retaining Klipper's standard
// config_neopixel/neopixel_update/neopixel_send command interface.
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include <string.h>

#include "basecmd.h"
#include "command.h"
#include "driver/rmt_encoder.h"
#include "driver/rmt_tx.h"
#include "esp_rom_sys.h"
#include "sched.h"

#define NEOPIXEL_RMT_RESOLUTION_HZ 10000000
#define NEOPIXEL_MAX_DATA_SIZE 192
#define NEOPIXEL_TX_TIMEOUT_MS 20
#define NEOPIXEL_RESET_US 80

struct neopixel_s {
    rmt_channel_handle_t channel;
    rmt_encoder_handle_t encoder;
    uint16_t data_size;
    uint8_t data[];
};

void
command_config_neopixel(uint32_t *args)
{
    uint32_t pin = args[1];
    uint16_t data_size = args[2];
    if (!data_size || data_size > NEOPIXEL_MAX_DATA_SIZE)
        shutdown("Invalid neopixel data_size");

    struct neopixel_s *n = oid_alloc(
        args[0], command_config_neopixel, sizeof(*n) + data_size);
    memset(n, 0, sizeof(*n) + data_size);
    n->data_size = data_size;

    rmt_tx_channel_config_t channel_config = {
        .gpio_num = pin,
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = NEOPIXEL_RMT_RESOLUTION_HZ,
        .mem_block_symbols = 64,
        .trans_queue_depth = 1,
    };
    if (rmt_new_tx_channel(&channel_config, &n->channel) != ESP_OK)
        shutdown("Unable to allocate neopixel RMT channel");

    rmt_bytes_encoder_config_t encoder_config = {
        .bit0 = {
            .level0 = 1,
            .duration0 = 3, // 0.3us high
            .level1 = 0,
            .duration1 = 9, // 0.9us low
        },
        .bit1 = {
            .level0 = 1,
            .duration0 = 9, // 0.9us high
            .level1 = 0,
            .duration1 = 3, // 0.3us low
        },
        .flags.msb_first = 1,
    };
    if (rmt_new_bytes_encoder(&encoder_config, &n->encoder) != ESP_OK)
        shutdown("Unable to allocate neopixel RMT encoder");
    if (rmt_enable(n->channel) != ESP_OK)
        shutdown("Unable to enable neopixel RMT channel");

    (void)args[3]; // generic bit-banger timing; RMT owns timing here
    (void)args[4];
}
DECL_COMMAND(command_config_neopixel, "config_neopixel oid=%c pin=%u"
             " data_size=%hu bit_max_ticks=%u reset_min_ticks=%u");

void
command_neopixel_update(uint32_t *args)
{
    struct neopixel_s *n = oid_lookup(args[0], command_config_neopixel);
    uint16_t pos = args[1];
    uint8_t data_len = args[2];
    if (pos + data_len > n->data_size)
        shutdown("Invalid neopixel update command");
    memcpy(&n->data[pos], command_decode_ptr(args[3]), data_len);
}
DECL_COMMAND(command_neopixel_update,
             "neopixel_update oid=%c pos=%hu data=%*s");

void
command_neopixel_send(uint32_t *args)
{
    struct neopixel_s *n = oid_lookup(args[0], command_config_neopixel);
    rmt_transmit_config_t transmit_config = {
        .loop_count = 0,
        .flags.eot_level = 0,
    };
    esp_err_t ret = rmt_transmit(
        n->channel, n->encoder, n->data, n->data_size, &transmit_config);
    if (ret == ESP_OK)
        ret = rmt_tx_wait_all_done(n->channel, NEOPIXEL_TX_TIMEOUT_MS);
    if (ret == ESP_OK)
        esp_rom_delay_us(NEOPIXEL_RESET_US);
    sendf("neopixel_result oid=%c success=%c", args[0], ret == ESP_OK);
}
DECL_COMMAND(command_neopixel_send, "neopixel_send oid=%c");
