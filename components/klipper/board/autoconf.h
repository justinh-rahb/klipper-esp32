// Copyright (C) 2024 Nikhil Robinson <nikhil@techprogeny.com>
// Copyright (C) 2026 Justin Hayes <justinh@rahb.ca> (ESP32-C3 modifications)
// Distributed under the terms of the GNU GPLv3 license.

#ifndef __AUTOCONF_H
#define __AUTOCONF_H

// Include ESP-IDF configuration
#include "sdkconfig.h"

// Ensure CONFIG_CLOCK_FREQ is defined with fallback
#ifndef CONFIG_CLOCK_FREQ
#ifdef CONFIG_ESP32_DEFAULT_CPU_FREQ_MHZ
#define CONFIG_CLOCK_FREQ (CONFIG_ESP32_DEFAULT_CPU_FREQ_MHZ * 1000000)
#elif defined(CONFIG_ESP32S2_DEFAULT_CPU_FREQ_MHZ)
#define CONFIG_CLOCK_FREQ (CONFIG_ESP32S2_DEFAULT_CPU_FREQ_MHZ * 1000000)
#elif defined(CONFIG_ESP32S3_DEFAULT_CPU_FREQ_MHZ)
#define CONFIG_CLOCK_FREQ (CONFIG_ESP32S3_DEFAULT_CPU_FREQ_MHZ * 1000000)
#elif defined(CONFIG_ESP32C3_DEFAULT_CPU_FREQ_MHZ)
#define CONFIG_CLOCK_FREQ (CONFIG_ESP32C3_DEFAULT_CPU_FREQ_MHZ * 1000000)
#elif defined(CONFIG_ESP32C2_DEFAULT_CPU_FREQ_MHZ)
#define CONFIG_CLOCK_FREQ (CONFIG_ESP32C2_DEFAULT_CPU_FREQ_MHZ * 1000000)
#elif defined(CONFIG_ESP32C6_DEFAULT_CPU_FREQ_MHZ)
#define CONFIG_CLOCK_FREQ (CONFIG_ESP32C6_DEFAULT_CPU_FREQ_MHZ * 1000000)
#elif defined(CONFIG_ESP32H2_DEFAULT_CPU_FREQ_MHZ)
#define CONFIG_CLOCK_FREQ (CONFIG_ESP32H2_DEFAULT_CPU_FREQ_MHZ * 1000000)
#else
// Fallback to 1MHz timer frequency (common for Klipper ESP32)
#define CONFIG_CLOCK_FREQ 1000000
#endif
#endif

// Compatibility macros for boolean configs that might not be defined
#ifndef CONFIG_MACH_ESP32
#define CONFIG_MACH_ESP32 1
#endif

#ifndef CONFIG_MACH_AVR
#define CONFIG_MACH_AVR 0
#endif

#ifndef CONFIG_MACH_ATSAM
#define CONFIG_MACH_ATSAM 0
#endif

#ifndef CONFIG_MACH_ATSAMD
#define CONFIG_MACH_ATSAMD 0
#endif

#ifndef CONFIG_MACH_LPC176X
#define CONFIG_MACH_LPC176X 0
#endif

#ifndef CONFIG_MACH_STM32
#define CONFIG_MACH_STM32 0
#endif

#ifndef CONFIG_MACH_HC32F460
#define CONFIG_MACH_HC32F460 0
#endif

#ifndef CONFIG_MACH_RP2040
#define CONFIG_MACH_RP2040 0
#endif

#ifndef CONFIG_MACH_PRU
#define CONFIG_MACH_PRU 0
#endif

#ifndef CONFIG_MACH_AR100
#define CONFIG_MACH_AR100 0
#endif

#ifndef CONFIG_MACH_LINUX
#define CONFIG_MACH_LINUX 0
#endif

#ifndef CONFIG_MACH_SIMU
#define CONFIG_MACH_SIMU 0
#endif

// String config defaults
#ifndef CONFIG_INITIAL_PINS
#define CONFIG_INITIAL_PINS ""
#endif

#ifndef CONFIG_USB_SERIAL_NUMBER
#define CONFIG_USB_SERIAL_NUMBER ""
#endif

#ifndef CONFIG_INLINE_STEPPER_HACK
#define CONFIG_INLINE_STEPPER_HACK 0
#endif

#ifndef CONFIG_HAVE_STRICT_TIMING
#define CONFIG_HAVE_STRICT_TIMING 0
#endif

#ifndef CONFIG_HAVE_BOOTLOADER_REQUEST
#define CONFIG_HAVE_BOOTLOADER_REQUEST 0
#endif

// generic/serial_irq.c publishes this value in the MCU dictionary. USB does
// not use a physical baud rate, but Klipper still requires the constant.
#ifndef CONFIG_SERIAL_BAUD
#ifdef CONFIG_KLIPPER_UART_BAUD_RATE
#define CONFIG_SERIAL_BAUD CONFIG_KLIPPER_UART_BAUD_RATE
#else
#define CONFIG_SERIAL_BAUD 250000
#endif
#endif

// Validate the project-owned console selection without aliasing ESP-IDF's
// CONFIG_CONSOLE_UART symbol (which caused pervasive macro redefinitions).
#if !defined(CONFIG_KLIPPER_CONSOLE_UART) && \
    !defined(CONFIG_KLIPPER_CONSOLE_USB_CDC)
#error "No console type configured. Enable either UART or USB CDC console in menuconfig."
#endif

#if defined(CONFIG_KLIPPER_CONSOLE_USB_CDC) && \
    !defined(CONFIG_SOC_USB_SERIAL_JTAG_SUPPORTED)
#error "USB CDC console selected but SOC doesn't support USB. Use UART console instead."
#endif


#endif // __AUTOCONF_H
