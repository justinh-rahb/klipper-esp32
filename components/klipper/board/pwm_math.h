#ifndef __ESP32_PWM_MATH_H
#define __ESP32_PWM_MATH_H

#include <stdint.h>

// Klipper supplies a PWM period in MCU clock ticks. ESP-IDF LEDC consumes a
// frequency in hertz. Round to the nearest integer frequency.
static inline uint32_t
pwm_frequency_for_cycle(uint32_t clock_frequency, uint32_t cycle_ticks)
{
    if (!clock_frequency || !cycle_ticks)
        return 0;
    return ((uint64_t)clock_frequency + cycle_ticks / 2) / cycle_ticks;
}

#endif
