# Roadmap

Copyright (C) 2026 Justin Hayes <justinh@rahb.ca>  
Distributed under the terms of the GNU GPLv3 license.

## Project direction

The goal is a dependable ESP32-family **secondary Klipper MCU** for sensors,
fans, LEDs, buttons, and printer accessories. ESP32-C3 is the reference target;
ESP32-S3 has completed initial hardware bring-up, and the original ESP32 remains
a planned target. It is not intended to become a general-purpose motion
controller.

The project will implement the Klipper command families that unlock useful
peripherals on those three chips. It will not chase command-count parity with
every Klipper MCU target.

“Supported” means that a capability:

1. builds in every profile where it is enabled;
2. is asserted in the generated Klipper protocol dictionary;
3. has host-side tests for timing or conversion logic where practical;
4. connects to Klippy and works on physical hardware;
5. has shutdown, disconnect, and reconnect behavior checked; and
6. has a documented example configuration.

## Current baseline

The current generated dictionaries contain 17 commands for `panda`, 20 for
`dev`, and 28 for `bentobox`.

| Capability | Status | Notes |
|---|---|---|
| Klipper identify, configuration, clock, uptime, reset, and shutdown | Validated | Includes long-running clock synchronization and a real 32-bit timer-rollover soak. |
| Scheduled digital output | Validated | Tested through Klippy on an ESP32-C3 development board. |
| Analog input | Firmware available | Physical ADC range, calibration, and fault behavior still need profile-specific validation. |
| UART and native USB Serial/JTAG transports | Validated | Profile selected; Klipper binary framing is isolated from ESP-IDF logging. |
| RMT NeoPixel | Validated on `dev` | Physical GPIO8 C3 and GPIO48 S3 LEDs have been exercised through Klippy. |
| ESP32-S3 target | Klippy bring-up validated | Native USB, identify/clock/uptime, host-service reconnect, and visible GPIO48 RMT pass on a dual-USB-C S3 board; rollover, ADC, and physical USB reconnect testing remain. |
| Hardware I2C | Builds on `bentobox` | BME280 and SGP40 command support is present; physical sensor validation remains. |
| LEDC hardware PWM | Builds on `bentobox` | Two independent 25 kHz fan outputs are configured; physical fan validation remains. |
| Panda Breath heater control | Locked out | Intentionally unavailable until the documented local safety interlocks are implemented and tested. |

## Priorities

### P0 — Finish and harden the current promise

- Bench-test the BentoBox profile with a real BME280, SGP40, and two 4-wire
  25 kHz PWM fans.
- Verify duty-cycle endpoints, inversion, startup, shutdown, MCU power loss,
  USB disconnect, and Klippy restart behavior.
- Validate ESP32-C3 ADC pins, attenuation, repeatability, and out-of-range
  shutdown behavior with real thermistors or known voltages.
- Run disconnect/reconnect and multi-hour soak tests on all three profiles.
- Record expected commands and responses per profile so protocol-surface
  regressions fail the build.
- Separate peripheral feature switches from product profiles. A generic board
  should be able to enable I2C, hardware PWM, SPI, or NeoPixel independently.

### P1 — Finish ESP32-S3 and add original ESP32

Make the chip target independent from the product profile before adding many
more peripheral command families. In particular, a `dev` role should be
buildable for `esp32c3`, `esp32s3`, or the original `esp32` without pretending
that C3-specific BentoBox or Panda Breath pin maps are portable.

- Add an explicit target argument to the build and keep separate build,
  sdkconfig, artifact, and dictionary paths for each target/profile pair.
- Generate the Klipper `MCU` dictionary identity and artifact names from the
  selected chip instead of hard-coding `esp32c3`.
- Move GPIO limits, reserved/strap pins, ADC channel maps, timer details, RMT,
  LEDC, I2C, and SPI capabilities behind target-specific definitions.
- Audit direct register access and ESP-IDF driver assumptions on all targets.
- Handle FreeRTOS task placement explicitly: C3 is single-core, while S3 and
  the original ESP32 require a deliberate core-affinity and interrupt plan.
- Keep Wi-Fi and Bluetooth disabled while scheduler jitter is characterized.
- Build every generic feature in a CI matrix for all three targets; product
  profiles remain limited to the hardware they actually describe.

Bring-up order:

1. **ESP32-S3:** UART plus native USB Serial/JTAG, base protocol, GPIO, ADC,
   timer rollover, RMT NeoPixel, I2C, and LEDC PWM.
2. **Original ESP32:** UART through a USB bridge, then the same non-USB
   peripheral surface with target-appropriate pin and timer handling.

Each target needs a real development board, a Klippy connection test, a
disconnect/reconnect test, and its own 32-bit clock-rollover soak before it is
called supported. USB OTG on S3 is not required for initial support; native USB
Serial/JTAG is the first transport target.

Completed S3 foundation:

- target/profile-separated C3 and S3 builds, sdkconfigs, artifacts, and MCU
  dictionary identities;
- target-aware GPIO validation, including rejection of the S3 GPIO22–25 gap;
- explicit S3 Klipper task affinity on core 0;
- real native-USB protocol and watchdog-stability probes;
- a dedicated Kalico connection, host-service restart/reconnect, and visible
  GPIO48 RMT NeoPixel sequence driven through Klippy G-code.

Remaining S3 qualification includes a scheduled digital GPIO test, ADC checks,
physical USB disconnect/reconnect recovery, and the 32-bit rollover soak.

### P2 — Inputs and fan feedback

Add the low-risk Klipper command families that make an ESP32-family MCU useful
as an accessory controller:

- `buttons`: debounced buttons, switches, door sensors, and simple digital
  inputs using Klipper's existing `buttons.c` polling implementation;
- `counter`: fan tachometer, flow sensor, and other moderate-rate edge counting
  using `pulse_counter.c`;
- profile-level pull-up, pull-down, boot-strap pin, and pin-conflict validation;
- fan RPM examples that pair one counter input with each PWM fan output.

Acceptance target: two PWM fans can be commanded from Klipper while both tach
signals are reported reliably in Fluidd/Mainsail, with button activity and I2C
polling running at the same time.

### P3 — SPI and common SPI sensors

The repository contains an inherited ESP32 SPI backend, but it is not currently
compiled and its fixed bus/pin assumptions have not been validated across the
three target chips. Treat it as a starting point, not existing support.

- Replace fixed SPI pin tables with explicit profile/Kconfig pin selection.
- Expose only usable controllers for the selected target and reject
  flash/PSRAM-reserved, strap, or conflicting pins.
- Enable Klipper's `spicmds` command family and optional software SPI.
- Validate mode 0–3, clock limits, chip-select polarity, full-duplex transfers,
  multiple devices, and shutdown cleanup.
- First device targets: MAX31855/MAX31856/MAX31865/MAX6675 thermocouple/RTD
  interfaces, then ADXL345 and LIS2DW accelerometers.

Device-specific MCU modules will be enabled only when they provide a real
benefit over generic SPI/I2C transactions and have hardware available for
testing.

### P4 — Additional accessory interfaces

Add these on demand, after the generic buses and inputs are solid:

- `tmcuart` for TMC driver configuration on native-USB profiles, with timing
  tests before it is used for an extruder;
- selected buffered sensor modules for high-rate accelerometers or load cells;
- software I2C as a separately tested fallback rather than an incidental side
  effect of a product profile;
- lightweight diagnostics such as `debug_ping`, without enabling arbitrary
  raw-memory access in normal builds.

LCD protocols, SDIO, CAN transport, OneWire, and uncommon sensor-specific
commands stay in the backlog until a concrete board or use case needs them.

### Stretch — One extruder stepper

A single extruder motor is a useful stretch goal, but it crosses a much higher
timing and safety bar than accessory I/O.

- Gate `stepper` and its required `trsync` support behind an experimental build
  option; do not include it in normal secondary-MCU profiles.
- Support one STEP/DIR/ENABLE channel first. X/Y/Z motion, kinematics, and
  endstop homing remain out of scope.
- Measure step-pulse width, direction setup/hold, sustained step rate, scheduler
  jitter, queue underruns, and USB traffic interference on a logic analyzer.
- Test full-speed extrusion, rapid acceleration changes, emergency stop,
  disconnect, reset, and 32-bit timer rollover with a sacrificial driver/motor.
- Add TMC UART only after its bit timing is independently validated.
- Keep heaters separate: adding an extruder stepper does not authorize heater
  outputs or weaken the Panda Breath relay lockout.

The extruder feature becomes supported only after an extended real-print test;
until then it must remain clearly labeled experimental.

## Explicitly out of scope

- General X/Y/Z motion control or replacing a printer's main MCU.
- Multi-axis synchronization, kinematics, and homing support.
- “All Klipper commands” as a goal by itself.
- Heater control without independent local thermal, fan, watchdog, and
  communication-loss interlocks.
- Wi-Fi or Bluetooth transport while deterministic timing and recovery remain
  unproven.
- Treating pin maps or successful builds as portable hardware validation across
  C3, S3, and the original ESP32.

## Suggested implementation order

| Order | Deliverable | Main Klipper modules | Hardware gate |
|---:|---|---|---|
| 1 | BentoBox physical validation and profile-independent feature flags | Existing core, `i2ccmds`, `pwmcmds` | BME280, SGP40, two PWM fans |
| 2 | Target/profile build separation and ESP32-S3 bring-up | Existing core and target board layer | ESP32-S3 development board |
| 3 | Original ESP32 bring-up | Existing core and target board layer | Original ESP32 development board with USB-UART bridge |
| 4 | Buttons and switches | `buttons.c` | Buttons, door/reed switch |
| 5 | Fan tach and edge counters | `pulse_counter.c` | Two tach-output fans or signal generator |
| 6 | Generic hardware/software SPI | `spicmds.c`, `spi_software.c` | Logic analyzer and SPI loopback/device on each target |
| 7 | Common SPI temperature and accelerometer devices | `thermocouple.c`, selected sensor modules | At least one real device per enabled module |
| 8 | TMC configuration transport | `tmcuart.c` | TMC2209-class driver and logic analyzer |
| 9 | Experimental single extruder | `stepper.c`, `trsync.c` | Driver, motor, logic analyzer, real print on each qualified target |

This ordering is intentionally driven by testable printer-accessory use cases,
not by how many commands it adds to the dictionary.
