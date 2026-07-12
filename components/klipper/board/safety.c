// Panda Breath heater safety boundary.
//
// The physical relay is deliberately locked off in this foundation build.
// Klipper protocol and timing can therefore be exercised on either a dev board
// or the real controller without permitting heater power before local PTC and
// airflow interlocks are implemented and validated.

#include "autoconf.h"
#include "panda_breath_pins.h"
#include "safety.h"

#include "command.h"
#include "driver/gpio.h"
#include "sched.h"

static volatile uint8_t relay_level;

void
panda_safety_early_init(void)
{
#if defined(CONFIG_PANDA_BREATH_HARDWARE)
    // Assert the safe state before FreeRTOS tasks, Klipper configuration, or
    // any communication is allowed to run.
    gpio_reset_pin(GPIO_RELAY);
    gpio_set_direction(GPIO_RELAY, GPIO_MODE_OUTPUT);
    gpio_set_level(GPIO_RELAY, 0);
    relay_level = 0;

    gpio_reset_pin(GPIO_FAN);
    gpio_set_direction(GPIO_FAN, GPIO_MODE_OUTPUT);
    gpio_set_level(GPIO_FAN, 0);
#endif
}

uint8_t
panda_safety_handles_pin(uint32_t pin)
{
#if defined(CONFIG_PANDA_BREATH_HARDWARE)
    return pin == GPIO_RELAY;
#else
    (void)pin;
    return 0;
#endif
}

void
panda_safety_write(uint32_t value)
{
#if defined(CONFIG_PANDA_BREATH_HARDWARE)
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
#else
    (void)value;
#endif
}

uint8_t
panda_safety_read(void)
{
    return relay_level;
}

void
panda_safety_shutdown(void)
{
#if defined(CONFIG_PANDA_BREATH_HARDWARE)
    gpio_set_level(GPIO_RELAY, 0);
    relay_level = 0;
#endif
}
DECL_SHUTDOWN(panda_safety_shutdown);
