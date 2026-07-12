// Panda Breath KlipperMCU firmware — entry point
//
// Adapts klipper_esp32 (nikhil-robinson) for the BIQU Panda Breath (ESP32-C3).
// Transport: UART0 via onboard CH340K USB-C bridge → Klipper MCU binary protocol.
// Fan control: internal TRIAC phase-angle (see board/fan.c), not exposed to Klipper.
//
// Copyright (C) 2024  Nikhil Robinson <nikhil@techprogeny.com> (original ESP32 port)
// ESP32-C3 / Panda Breath adaptation: see project contributors
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "internal.h"  // console_setup
#include "safety.h"    // panda_safety_early_init
#include "sched.h"     // sched_main
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_task_wdt.h"

// Declare the fan init function from board/fan.c
void fan_init(void);

static void main_task(void *pvparameters)
{
    // A stalled Klipper scheduler must reset the MCU, returning the relay to
    // its hardware-pulldown boot state. irq_wait() feeds this watchdog.
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));

    // Start internal TRIAC fan control before Klipper scheduler.
    // The fan monitors the heater relay GPIO and runs a phase-angle duty
    // cycle via the zero-crossing detector — entirely invisible to Klipper.
#if defined(CONFIG_PANDA_BREATH_HARDWARE) && \
    defined(CONFIG_PANDA_BREATH_LEGACY_FAN)
    fan_init();
#endif

    console_setup(NULL);

    sched_main();

    vTaskDelete(NULL);
}

void app_main(void)
{
    panda_safety_early_init();

    // ESP32-C3 is single-core; pinToCore=0 is the only valid option
    xTaskCreatePinnedToCore(main_task, "main_task", 16384, NULL, 20, NULL, 0);
}
