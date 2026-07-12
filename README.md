# Panda Breath Klipper MCU firmware

Experimental ESP32-C3 firmware that implements the subset of Klipper's MCU
protocol needed for a chamber heater: base commands, scheduled digital output,
and ADC sampling.

## Current safety state

The firmware builds in two profiles:

- `dev` uses native USB Serial/JTAG and initializes no Panda Breath pins.
- `panda` uses UART0 through the onboard CH340K and forces the physical relay
  and TRIAC gate low before the scheduler starts.

The `panda` profile currently **locks the heater relay off**. Any request to set
GPIO18 high causes a Klipper shutdown. Do not remove this lockout until all of
the following exist and have hardware tests:

- calibrated chamber and PTC thermistor conversion;
- open/short detection for both thermistors;
- a latched local PTC overtemperature cutoff;
- fan startup and zero-crossing interlocks;
- MCU watchdog and communication-timeout fault injection;
- verified relay-off behavior during boot, reset, panic, and shutdown.

The legacy `esp_timer` TRIAC implementation is disabled by default and retained
only as a reference while a hardware-timed replacement is developed.

The `dev` profile additionally exposes Klipper's standard NeoPixel commands
through the ESP32-C3 RMT peripheral. This keeps WS2812 sub-microsecond waveform
timing independent of Klipper's intentional 1MHz scheduling clock. The feature
is excluded from the `panda` profile.

## Build

Prerequisites:

1. ESP-IDF 5.3.x with the ESP32-C3 RISC-V toolchain.
2. The Klipper submodule initialized:

   ```sh
   git submodule update --init --recursive
   ```

3. ESP-IDF exported into the shell:

   ```sh
   source ~/esp/esp-idf/export.sh
   ```

Build the safe development-board image:

```sh
./build.sh dev
```

Build the real-board image with the heater still locked off:

```sh
./build.sh panda
```

Klipper's dictionary is generated from compile-time request sections. The
wrapper intentionally invokes ESP-IDF twice: the first pass generates the
dictionary source, and the second pass compiles it into the final image.

Artifacts are written to `build-<profile>/`:

- `panda_breath.bin`
- `panda_breath.elf`
- `esp-idf/klipper/klipper.dict`

The dictionary is embedded in the MCU image and transferred during Klipper's
identify handshake; it does not need to be copied to the Klipper host.

## Flash the development board

```sh
idf.py -B build-dev -p /dev/cu.usbmodemXXXX flash
```

Some boards require manual ROM-loader entry: hold **BOOT**, tap **RESET**, then
release **BOOT** before running the flash command.

For a macOS smoke test, install `pyserial` into your test environment and run:

```sh
python3 probe_mcu.py /dev/cu.usbmodemXXXX
```

The probe performs Klipper identify, uptime, clock, and configuration queries,
then holds the connection idle long enough to catch a task-watchdog reset. On
native USB it allows one second for the board's automatic open/reset cycle.
It never configures GPIOs or sends output commands.

Use `dev-printer.cfg.example` for a full protocol-only Klippy connection test
from a Linux Klipper host. Klipper's host C helper is Linux-specific, so that
full test cannot run directly on macOS.
