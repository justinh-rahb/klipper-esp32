// Copyright (C) 2026 Justin Hayes <justinh@rahb.ca>
// Distributed under the terms of the GNU GPLv3 license.

#ifndef __ESP32_TIMER_MATH_H
#define __ESP32_TIMER_MATH_H

#include <stdint.h>

// Give GPTimer enough lead time to install an alarm that is already due or
// became too close while returning from Klipper's software timer dispatcher.
#define ESP32_TIMER_MIN_ALARM_TICKS 5U

// Convert Klipper's wrapping 32-bit timestamp into the corresponding future
// 64-bit GPTimer count. Klipper guarantees scheduled timestamps are within one
// signed 32-bit interval, so a negative delta means the timer is late rather
// than almost one full epoch in the future.
static inline uint64_t
timer_alarm_count_for(uint64_t now, uint32_t next)
{
    int32_t delta = (int32_t)(next - (uint32_t)now);
    if (delta < (int32_t)ESP32_TIMER_MIN_ALARM_TICKS)
        delta = ESP32_TIMER_MIN_ALARM_TICKS;
    return now + (uint32_t)delta;
}

#endif // timer_math.h
