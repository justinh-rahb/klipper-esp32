// ESP32 hardware I2C support for Klipper MCU commands.
//
// Copyright (C) 2024 Nikhil Robinson <nikhil@techprogeny.com>
// Copyright (C) 2026 Justin Hayes <justinh@rahb.ca> (ESP32-C3 integration)
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "autoconf.h"
#include "command.h"
#include "driver/i2c_master.h"
#include "gpio.h"
#include "i2ccmds.h"
#include "sched.h"

#define STRINGIFY_INNER(value) #value
#define STRINGIFY(value) STRINGIFY_INNER(value)
#define GPIO_NAME(value) "GPIO_NUM_" STRINGIFY(value)
#define I2C_TIMEOUT_MS 50

DECL_ENUMERATION("i2c_bus", "i2c0", 0);
DECL_CONSTANT_STR("BUS_PINS_i2c0",
                  GPIO_NAME(CONFIG_KLIPPER_I2C0_SDA_PIN) ","
                  GPIO_NAME(CONFIG_KLIPPER_I2C0_SCL_PIN));

static i2c_master_bus_handle_t i2c0_handle;

static int
i2c_result(esp_err_t result)
{
    if (result == ESP_OK)
        return I2C_BUS_SUCCESS;
    if (result == ESP_ERR_TIMEOUT)
        return I2C_BUS_TIMEOUT;
    return I2C_BUS_NACK;
}

struct i2c_config
i2c_setup(uint32_t bus, uint32_t rate, uint8_t addr)
{
    if (bus != 0)
        shutdown("Invalid i2c bus");
    if (!rate || rate > 1000000)
        shutdown("Invalid i2c rate");

    if (!i2c0_handle) {
        i2c_master_bus_config_t bus_config = {
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .i2c_port = I2C_NUM_0,
            .scl_io_num = CONFIG_KLIPPER_I2C0_SCL_PIN,
            .sda_io_num = CONFIG_KLIPPER_I2C0_SDA_PIN,
            .glitch_ignore_cnt = 7,
            .flags.enable_internal_pullup = true,
        };
        if (i2c_new_master_bus(&bus_config, &i2c0_handle) != ESP_OK)
            shutdown("Unable to initialize i2c bus");
    }

    i2c_device_config_t device_config = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = addr,
        .scl_speed_hz = rate,
    };
    i2c_master_dev_handle_t device_handle;
    if (i2c_master_bus_add_device(i2c0_handle, &device_config,
                                  &device_handle) != ESP_OK)
        shutdown("Unable to add i2c device");

    return (struct i2c_config){.handle = device_handle};
}

int
i2c_write(struct i2c_config config, uint8_t write_len, uint8_t *write)
{
    return i2c_result(i2c_master_transmit(config.handle, write, write_len,
                                          I2C_TIMEOUT_MS));
}

int
i2c_read(struct i2c_config config, uint8_t reg_len, uint8_t *reg,
         uint8_t read_len, uint8_t *read)
{
    esp_err_t result;
    if (reg_len)
        result = i2c_master_transmit_receive(config.handle, reg, reg_len,
                                             read, read_len, I2C_TIMEOUT_MS);
    else
        result = i2c_master_receive(config.handle, read, read_len,
                                    I2C_TIMEOUT_MS);
    return i2c_result(result);
}
