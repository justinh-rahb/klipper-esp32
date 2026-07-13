#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "timer_math.h"

static void
expect_alarm(uint64_t now, uint32_t next, uint64_t expected)
{
    uint64_t actual = timer_alarm_count_for(now, next);
    if (actual != expected) {
        fprintf(stderr,
                "now=%llu next=%u: expected %llu, got %llu\n",
                (unsigned long long)now, next,
                (unsigned long long)expected, (unsigned long long)actual);
    }
    assert(actual == expected);
}

int
main(void)
{
    // A normal future alarm remains exact.
    expect_alarm(1000000ULL, 1000100U, 1000100ULL);

    // Late, equal, and too-close alarms become imminent, not next-epoch.
    expect_alarm(1000100ULL, 1000090U,
                 1000100ULL + ESP32_TIMER_MIN_ALARM_TICKS);
    expect_alarm(1000100ULL, 1000100U,
                 1000100ULL + ESP32_TIMER_MIN_ALARM_TICKS);
    expect_alarm(1000100ULL, 1000103U,
                 1000100ULL + ESP32_TIMER_MIN_ALARM_TICKS);

    // A genuinely future timestamp across the 32-bit rollover maps forward.
    expect_alarm(0x00000000fffffff0ULL, 0x00000010U,
                 0x0000000100000010ULL);

    // A timestamp shortly before an already-completed rollover is overdue.
    expect_alarm(0x0000000100000010ULL, 0xfffffff0U,
                 0x0000000100000010ULL + ESP32_TIMER_MIN_ALARM_TICKS);

    // Mapping continues to work after more than one 32-bit epoch.
    expect_alarm(0x0000000200000100ULL, 0x00000200U,
                 0x0000000200000200ULL);

    puts("timer rollover tests passed");
    return 0;
}
