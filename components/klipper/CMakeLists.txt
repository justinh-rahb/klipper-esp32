set(SOURCES
    # Shared ESP32-C3 board layer
    board/adc.c
    board/console.c
    board/gpio.c
    board/internal.c
    board/timer.c

    # Klipper MCU core sources
    klipper/src/adccmds.c
    klipper/src/basecmd.c
    klipper/src/command.c
    klipper/src/gpiocmds.c
    klipper/src/initial_pins.c
    klipper/src/sched.c
    klipper/src/generic/alloc.c
    klipper/src/generic/crc16_ccitt.c
    klipper/src/generic/serial_irq.c
    klipper/src/generic/timer_irq.c
)

set(KLIPPER_INCLUDE_DIRS
    klipper/src
    klipper/src/generic
    .
    board
)

if(CONFIG_PANDA_BREATH_HARDWARE)
    list(APPEND SOURCES board_profiles/panda_breath/safety.c)
    list(APPEND KLIPPER_INCLUDE_DIRS board_profiles/panda_breath)
endif()

if(CONFIG_PANDA_BREATH_LEGACY_FAN)
    list(APPEND SOURCES board_profiles/panda_breath/fan.c)
endif()

if(CONFIG_KLIPPER_RMT_NEOPIXEL)
    list(APPEND SOURCES board/neopixel_rmt.c)
endif()

if(CONFIG_BENTOBOX_SUPERMINI_HARDWARE)
    list(APPEND SOURCES
        board/hard_pwm.c
        board/i2c.c
        klipper/src/i2ccmds.c
        klipper/src/i2c_software.c
        klipper/src/pwmcmds.c
    )
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(EXTRACT_SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/extract_compile_time_requests.py)
set(CTR_FILE ${CMAKE_CURRENT_BINARY_DIR}/compile_time_request.c)

if(NOT EXISTS ${CTR_FILE})
    # Klipper's dictionary source is generated from sections in the other
    # compiled objects. Provide link-safe stubs for the first pass; build.sh
    # performs a second pass that compiles the generated implementation.
    file(WRITE ${CTR_FILE} [[
#include <stdint.h>
#include "command.h"

const struct command_parser command_index[] = {};
const uint16_t command_index_size = 0;
const uint8_t command_identify_data[] = {0};
const uint32_t command_identify_size = 0;

const struct command_encoder *ctr_lookup_encoder(const char *str) { return 0; }
const struct command_encoder *ctr_lookup_output(const char *str) { return 0; }
uint8_t ctr_lookup_static_string(const char *str) { return 0; }
void ctr_run_initfuncs(void) {}
void ctr_run_taskfuncs(void) {}
void ctr_run_shutdownfuncs(void) {}
]])
endif()

list(APPEND SOURCES ${CTR_FILE})

idf_component_register(
    SRCS ${SOURCES}
    INCLUDE_DIRS ${KLIPPER_INCLUDE_DIRS}
    # driver provides UART and native USB Serial/JTAG transports.
    REQUIRES driver esp_adc esp_driver_rmt esp_vfs_console esp_timer esp_system
)

add_custom_command(
    TARGET ${COMPONENT_LIB} PRE_BUILD
    COMMAND ${Python3_EXECUTABLE} ${EXTRACT_SCRIPT}
        ${CMAKE_CURRENT_BINARY_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${COMPONENT_LIB}
        "${CMAKE_C_COMPILER};${CMAKE_ASM_COMPILER};${CMAKE_LINKER};${CMAKE_OBJCOPY};${CMAKE_OBJDUMP};${CMAKE_STRIP}"
        --python ${Python3_EXECUTABLE}
        --objcopy ${CMAKE_OBJCOPY}
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
    COMMENT "Generating compile_time_request.c from object files"
    VERBATIM
)
