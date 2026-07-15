# Klipper MCU firmware for ESP32-C3

An experimental ESP-IDF port of Klipper's MCU firmware for ESP32-C3 boards.
It began as a Panda Breath chamber-heater controller, but the shared MCU core
is now independent of that product. Hardware-specific behavior is selected by
a build profile.

The port currently supports Klipper's base protocol, scheduled digital output,
ADC sampling, native USB Serial/JTAG or UART transport, ESP32-C3 RMT NeoPixel
output, hardware I2C, and LEDC hardware PWM. It is based on
[`nikhil-robinson/klipper_esp32`](https://github.com/nikhil-robinson/klipper_esp32)
and its Klipper fork.

## Profiles

| Profile | Target | Transport | Extra peripherals |
|---|---|---|---|
| `dev` | Generic ESP32-C3 development board | Native USB Serial/JTAG | GPIO8 NeoPixel |
| `bentobox` | ESP32-C3 SuperMini BentoBox controller | Native USB Serial/JTAG | I2C, two hardware-PWM fans, GPIO8 NeoPixel |
| `panda` | BIQU Panda Breath controller | UART0 through CH340K | Relay lockout and board-specific safety foundation |

Example Klipper configuration lives in [`config/`](config/). Profile-specific
ESP-IDF defaults live in [`profiles/`](profiles/). Product code is isolated in
[`components/klipper/board_profiles/`](components/klipper/board_profiles/).

## Validation status

The `dev` profile has been tested as a Linux/Kalico secondary MCU, including
clock synchronization, watchdog continuity, a physical GPIO8 WS2812, and a
real soak across the 32-bit timer rollover at 1 MHz. The rollover run stayed
connected through the 71.6-minute boundary and accepted a post-rollover status
LED command.

The timer bridge treats Klipper clocks as wrapping 32-bit values over the
ESP32-C3's 64-bit GPTimer. Slightly overdue timestamps are clamped to an
imminent alarm instead of being mistaken for the next 32-bit epoch. Host tests
cover future and overdue timestamps on both sides of rollover.

The `bentobox` profile builds and exposes the MCU commands needed for a BME280,
SGP40, and two 25 kHz 4-wire fan PWM signals. It has not yet been validated
with those physical peripherals.

## Panda Breath safety boundary

The `panda` profile is experimental and **locks the heater relay off**. Any
request to set GPIO18 high triggers a Klipper shutdown. Do not remove this
lockout or energize the heater until the board has independently tested:

- calibrated chamber and PTC thermistor conversion;
- open/short detection for both thermistors;
- a latched local PTC overtemperature cutoff;
- fan startup and zero-crossing interlocks;
- MCU watchdog and communication-timeout fault injection;
- relay-off behavior during boot, reset, panic, and shutdown.

The legacy `esp_timer` TRIAC implementation is disabled by default and retained
only as a reference while a hardware-timed replacement is developed.

## Build

Requirements:

- ESP-IDF 5.3.x with the ESP32-C3 RISC-V toolchain;
- Python 3;
- the Klipper submodule initialized.

```sh
git submodule update --init --recursive
source ~/esp/esp-idf/export.sh
./build.sh dev
./build.sh bentobox
./build.sh panda
```

Each invocation uses a separate `build-<profile>/` directory and validates the
generated Klipper protocol dictionary. The wrapper intentionally invokes
ESP-IDF twice: pass one generates Klipper's compile-time request source and
pass two compiles it into the final image.

Artifacts include:

- `build-<profile>/klipper_esp32c3.bin`
- `build-<profile>/klipper_esp32c3.elf`
- `build-<profile>/esp-idf/klipper/klipper.dict`

The dictionary is embedded in the MCU image and transferred during Klipper's
identify handshake; it does not need to be copied to the host.

## Flash and probe a development board

```sh
idf.py -B build-dev -p /dev/cu.usbmodemXXXX flash
python3 probe_mcu.py /dev/cu.usbmodemXXXX
```

Some boards require manual ROM-loader entry: hold **BOOT**, tap **RESET**, then
release **BOOT** before flashing. The probe performs identify, uptime, clock,
and configuration queries without configuring outputs. Add `--neopixel-pin 8`
for the dev-only RMT NeoPixel test.

For a full Klippy connection on Linux, start from [`config/dev.cfg`](config/dev.cfg).
ESP32-C3 pin names are dictionary enumerations such as `GPIO_NUM_8`; names like
`gpio8` are not accepted.

## BentoBox profile

The reference SuperMini wiring uses GPIO4/GPIO5 for a shared hardware I2C bus
and GPIO0/GPIO1 for two external open-collector fan PWM interfaces. The
Nevermore Mini combined sensor board normally places its BME280 at `0x77` and
SGP40 at `0x59`.

Klipper has a built-in BME280 driver. The example uses
[`thetic/klipper-sgp40`](https://github.com/thetic/klipper-sgp40) for the SGP40;
check that module's Klipper/Kalico version requirements before installation.
See [`config/bentobox.cfg`](config/bentobox.cfg) for wiring constraints, sensor
configuration, Fluidd/Mainsail-visible values, and fan G-code.

## Tests

```sh
sh tests/run_timer_math_test.sh
sh tests/run_pwm_math_test.sh
python3 -m py_compile probe_mcu.py validate_build.py
```

The profile build itself also runs `validate_build.py` against the emitted MCU
dictionary.

## License

GNU GPLv3. See [`LICENSE`](LICENSE).
