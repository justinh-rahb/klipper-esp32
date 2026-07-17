// Klipper MCU firmware for the original ESP32, ESP32-C3, and ESP32-S3
//
// Adapts klipper_esp32 (nikhil-robinson) for ESP32-family board profiles.
//
// Copyright (C) 2024  Nikhil Robinson <nikhil@techprogeny.com> (original ESP32 port)
// Copyright (C) 2026  Justin Hayes <justinh@rahb.ca> (ESP32-family adaptation)
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

    // Core 0 is the C3's only core and the deliberate Klipper core on the
    // dual-core original ESP32 and S3. Pinning avoids scheduler migrations.
    xTaskCreatePinnedToCore(main_task, "main_task", 16384, NULL, 20, NULL, 0);
}
