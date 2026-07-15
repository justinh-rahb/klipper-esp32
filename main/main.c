// Klipper MCU firmware for ESP32-C3 — entry point
//
// Adapts klipper_esp32 (nikhil-robinson) for ESP32-C3 board profiles.
//
// Copyright (C) 2024  Nikhil Robinson <nikhil@techprogeny.com> (original ESP32 port)
// ESP32-C3 adaptation: see project contributors
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "internal.h"  // console_setup
#include "sched.h"     // sched_main
#ifdef CONFIG_PANDA_BREATH_HARDWARE
#include "safety.h"    // panda_safety_early_init
#endif
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_task_wdt.h"

#if defined(CONFIG_PANDA_BREATH_HARDWARE) && \
    defined(CONFIG_PANDA_BREATH_LEGACY_FAN)
void fan_init(void);
#endif

static void main_task(void *pvparameters)
{
    // A stalled Klipper scheduler must reset the MCU, returning the relay to
    // its hardware-pulldown boot state. irq_wait() feeds this watchdog.
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));

#if defined(CONFIG_PANDA_BREATH_HARDWARE) && \
    defined(CONFIG_PANDA_BREATH_LEGACY_FAN)
    // Start the profile's internal TRIAC fan control before the scheduler.
    fan_init();
#endif

    console_setup(NULL);

    sched_main();

    vTaskDelete(NULL);
}

void app_main(void)
{
#ifdef CONFIG_PANDA_BREATH_HARDWARE
    panda_safety_early_init();
#endif

    // ESP32-C3 is single-core; pinToCore=0 is the only valid option
    xTaskCreatePinnedToCore(main_task, "main_task", 16384, NULL, 20, NULL, 0);
}
