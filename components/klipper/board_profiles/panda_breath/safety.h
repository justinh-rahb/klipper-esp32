#ifndef __PANDA_BREATH_SAFETY_H
#define __PANDA_BREATH_SAFETY_H

#include <stdint.h>

// Called from app_main before the Klipper task or protocol starts.
void panda_safety_early_init(void);

// GPIO interception for the physical heater relay.
uint8_t panda_safety_handles_pin(uint32_t pin);
void panda_safety_write(uint32_t value);
uint8_t panda_safety_read(void);

#endif
