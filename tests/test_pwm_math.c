#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "../components/klipper/board/pwm_math.h"

int
main(void)
{
    assert(pwm_frequency_for_cycle(1000000, 40) == 25000);
    assert(pwm_frequency_for_cycle(1000000, 10000) == 100);
    assert(pwm_frequency_for_cycle(1000000, 100000) == 10);
    assert(pwm_frequency_for_cycle(1000000, 0) == 0);
    assert(pwm_frequency_for_cycle(0, 40) == 0);
    puts("pwm math tests passed");
    return 0;
}
