// Esp32 internal commands
//
// Copyright (C) 2024  Nikhil Robinson <nikhil@techprogeny.com>
// Copyright (C) 2026  Justin Hayes <justinh@rahb.ca> (ESP32-family modifications)
//
// This file may be distributed under the terms of the GNU GPLv3 license.

// Unless required by applicable law or agreed to in writing, this
// software is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
// CONDITIONS OF ANY KIND, either express or implied.

#include "internal.h" // NVIC_SystemReset
#include "autoconf.h"       // CONFIG_FLASH_APPLICATION_ADDRESS
#include "irq.h"      // irq_disable
#include "command.h"        // DECL_COMMAND_FLAGS
#include "esp_system.h"
#include "sched.h"          // sched_is_shutdown

#if CONFIG_IDF_TARGET_ESP32
#define KLIPPER_MCU_NAME "esp32"
#elif CONFIG_IDF_TARGET_ESP32C3
#define KLIPPER_MCU_NAME "esp32c3"
#elif CONFIG_IDF_TARGET_ESP32S3
#define KLIPPER_MCU_NAME "esp32s3"
#else
#error "Unsupported ESP32 target"
#endif

DECL_CONSTANT_STR("MCU", KLIPPER_MCU_NAME);

void command_reset(uint32_t *args) { esp_restart(); }
DECL_COMMAND_FLAGS(command_reset, HF_IN_SHUTDOWN, "reset");

void command_config_reset(uint32_t *args)
{
  if (!sched_is_shutdown())
    shutdown("config_reset only available when shutdown");
  esp_restart();
}
DECL_COMMAND_FLAGS(command_config_reset, HF_IN_SHUTDOWN, "config_reset");
