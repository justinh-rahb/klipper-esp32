// Panda Breath heater safety boundary.
//
// Copyright (C) 2026 Justin Hayes <justinh@rahb.ca>
//
// The physical relay is deliberately locked off in this foundation build.
// Klipper protocol and timing can therefore be exercised on either a dev board
// or the real controller without permitting heater power before local PTC and
// airflow interlocks are implemented and validated.
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "autoconf.h"
#include "pins.h"
#include "safety.h"

#include "command.h"
#include "driver/gpio.h"
#include "sched.h"

static volatile uint8_t relay_level;

void
panda_safety_early_init(void)
{
    // Assert the safe state before FreeRTOS tasks, Klipper configuration, or
    // any communication is allowed to run.
    gpio_reset_pin(GPIO_RELAY);
    gpio_set_direction(GPIO_RELAY, GPIO_MODE_OUTPUT);
    gpio_set_level(GPIO_RELAY, 0);
    relay_level = 0;

    gpio_reset_pin(GPIO_FAN);
    gpio_set_direction(GPIO_FAN, GPIO_MODE_OUTPUT);
    gpio_set_level(GPIO_FAN, 0);
}

uint8_t
panda_safety_handles_pin(uint32_t pin)
{
    return pin == GPIO_RELAY;
}

void
panda_safety_write(uint32_t value)
{
    if (value) {
        // This is intentionally a latched Klipper shutdown, not a silent
        // ignored write: an attempted heat command must be visible in testing.
        gpio_set_level(GPIO_RELAY, 0);
        relay_level = 0;
        try_shutdown("Panda heater safety interlocks not armed");
        return;
    }
    gpio_set_level(GPIO_RELAY, 0);
    relay_level = 0;
}

uint8_t
panda_safety_read(void)
{
    return relay_level;
}

void
panda_safety_shutdown(void)
{
    gpio_set_level(GPIO_RELAY, 0);
    relay_level = 0;
}
DECL_SHUTDOWN(panda_safety_shutdown);
