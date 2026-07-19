# Klipper MCU firmware for ESP32, ESP32-C3, and ESP32-S3

An experimental ESP-IDF port of Klipper's MCU firmware for ESP32-family boards.
It began as a Panda Breath chamber-heater controller, but the shared MCU core
is now independent of that product. Hardware-specific behavior is selected by
a build profile, while the chip is selected independently as a build target.

The ESP32-family adaptation, board profiles, and validation tooling in this
repository, including the ESP32-S3 and modern original-ESP32 target work, are
maintained by Justin Hayes.
The port currently supports
Klipper's base protocol, scheduled digital output,
ADC sampling, native USB Serial/JTAG or UART transport, ESP32 RMT NeoPixel
output, hardware I2C, and LEDC hardware PWM. It is based on
[`nikhil-robinson/klipper_esp32`](https://github.com/nikhil-robinson/klipper_esp32)
and its Klipper fork.

## Profiles

| Profile | Target | Transport | Extra peripherals |
|---|---|---|---|
| `dev` | Original ESP32 development board | UART0 over USB-UART bridge | Base protocol, GPIO, ADC |
| `dev` | Generic ESP32-C3 or ESP32-S3 development board | Native USB Serial/JTAG | RMT NeoPixel |
| `bentobox` | ESP32-C3 SuperMini BentoBox controller | Native USB Serial/JTAG | I2C, two hardware-PWM fans, GPIO8 NeoPixel |
| `panda` | BIQU Panda Breath controller | UART0 through CH340K | Relay lockout and board-specific safety foundation |

Example Klipper configuration lives in [`config/`](config/). Profile-specific
ESP-IDF defaults live in [`profiles/`](profiles/) and chip defaults in
[`targets/`](targets/). Product code is isolated in
[`components/klipper/board_profiles/`](components/klipper/board_profiles/).

## Validation status

The `dev` profile has been tested as a Linux/Kalico secondary MCU, including
clock synchronization, watchdog continuity, a physical GPIO8 WS2812, and a
real soak across the 32-bit timer rollover at 1 MHz. The rollover run stayed
connected through the 71.6-minute boundary and accepted a post-rollover status
LED command.

ESP32-S3 hardware and Klippy bring-up is also complete on a dual-USB-C
ESP32-S3-WROOM-1 board with 16 MB flash and 8 MB embedded PSRAM. The native
USB Serial/JTAG transport completed identify, clock, uptime, configuration,
and watchdog-stability probes. A dedicated Kalico instance configured the MCU,
reconnected after its host service restarted, and drove a visible RGB sequence
through the onboard GPIO48 addressable LED. The S3 scheduler is deliberately
pinned to core 0. A physical USB disconnect/reconnect test, ADC validation, and
rollover soak are still required before the S3 meets the roadmap's complete
support definition.

Initial original-ESP32 hardware bring-up is complete on an ESP32-D0WDQ6
revision 1 development board with a CP2102 USB-UART bridge and 4 MB flash. The
UART0 transport on GPIO1/GPIO3 completed identify, dictionary transfer, clock,
uptime, configuration-state, and watchdog-stability probes at 250000 baud. The
firmware reports a distinct `esp32` MCU identity and exposes the original
chip's 40-entry GPIO number range with runtime rejection of invalid and
input-only outputs. A real Klippy connection, scheduled GPIO test, ADC checks,
disconnect/reconnect test, and rollover soak remain before this target is
called fully supported.

The timer bridge treats Klipper clocks as wrapping 32-bit values over the
ESP32 family's 64-bit GPTimer. Slightly overdue timestamps are clamped to an
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

- ESP-IDF 5.3.x with the toolchain for each selected target;
- Python 3;
- the Klipper submodule initialized.

```sh
git submodule update --init --recursive
source ~/esp/esp-idf/export.sh
./build.sh dev
./build.sh dev esp32
./build.sh dev esp32s3
./build.sh bentobox
./build.sh panda
```

Omitting the target keeps the existing ESP32-C3 default. Only the generic
`dev` profile is portable to the original ESP32 and S3; the `bentobox` and
`panda` product profiles are rejected for non-C3 targets.

Each invocation uses a separate `build-<target>-<profile>/` directory and
validates the generated Klipper protocol dictionary. The wrapper intentionally
invokes ESP-IDF twice: pass one generates Klipper's compile-time request source
and pass two compiles it into the final image.

Artifacts include:

- `build-<target>-<profile>/klipper_<target>.bin`
- `build-<target>-<profile>/klipper_<target>.elf`
- `build-<target>-<profile>/esp-idf/klipper/klipper.dict`

The dictionary is embedded in the MCU image and transferred during Klipper's
identify handshake; it does not need to be copied to the host.

## Flash and probe a development board

```sh
idf.py -B build-esp32c3-dev -p /dev/cu.usbmodemXXXX flash
python3 probe_mcu.py /dev/cu.usbmodemXXXX
```

Some boards require manual ROM-loader entry: hold **BOOT**, tap **RESET**, then
release **BOOT** before flashing. The probe performs identify, uptime, clock,
and configuration queries without configuring outputs. Add `--neopixel-pin 8`
for the dev-only RMT NeoPixel test.

For a full Klippy connection on Linux, start from [`config/dev.cfg`](config/dev.cfg).
ESP32-C3 pin names are dictionary enumerations such as `GPIO_NUM_8`; names like
`gpio8` are not accepted.

For the tested S3 board, plug into the connector marked **USB**, not **COM**,
then build, flash, and probe with:

```sh
./build.sh dev esp32s3
idf.py -B build-esp32s3-dev -p /dev/cu.usbmodemXXXX flash
python3 probe_mcu.py /dev/cu.usbmodemXXXX --neopixel-pin 48
```

Start the host configuration from [`config/dev-s3.cfg`](config/dev-s3.cfg).
The tested board follows the
[original ESP32-S3-DevKitC-1 layout](https://docs.espressif.com/projects/esp-idf/en/v5.2/esp32s3/hw-reference/esp32s3/user-guide-devkitc-1-v1.0.html),
whose RGB LED is on GPIO48. Espressif's
[later v1.1 board](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html)
moved it to GPIO38. S3 pin names use the same `GPIO_NUM_<n>` form; GPIO22
through GPIO25 do not exist on S3 and are rejected by the firmware if requested.

For an original ESP32 board with a USB-UART bridge, build, flash, and probe the
bridge device instead. The tested CP2102 appeared as `/dev/cu.usbserial-0001`
on macOS:

```sh
./build.sh dev esp32
idf.py -B build-esp32-dev -p /dev/cu.usbserial-0001 flash
python probe_mcu.py /dev/cu.usbserial-0001
```

The target uses UART0 at 250000 baud: GPIO1 is TX and GPIO3 is RX. Start a
Linux Klippy configuration from [`config/dev-esp32.cfg`](config/dev-esp32.cfg)
and replace its example `/dev/serial/by-id/` path with the stable path reported
for your bridge. A plain onboard LED, when present, is often on GPIO2; it is not
enabled by default because GPIO2 is also a boot-strapping pin and board layouts
vary. The original ESP32 image deliberately omits NeoPixel commands until its
RMT implementation has target-specific hardware validation.

## Hardware test harnesses

Beyond `probe_mcu.py`, these scripts exercise the MCU over the Klipper binary
protocol. Each exits non-zero on failure so they can gate CI, and all take the
serial device as their first argument (except `reconnect_test.py`, which
auto-resolves the CH340 bridge):

```sh
python3 hw_test.py /dev/ttyUSB0          # digital-out, ADC, and heater-relay lockout
python3 latency_probe.py /dev/ttyUSB0    # true serial RTT + back-to-back burst timing
python3 rollover_soak.py                 # ~71 min 32-bit timer rollover soak
python3 reconnect_test.py                # USB re-enumeration / reboot recovery (needs sudo)
python3 run_klippy_test.py config/dev-panda-klippy.cfg   # full real-Klippy host connection
```

`latency_probe.py` reports first-byte and full-reply RTT plus a burst test that
distinguishes a shared pipeline (transport) delay from per-command work — it is
the tool behind the CH340 latency findings in
[`HARDWARE_BRINGUP.md`](HARDWARE_BRINGUP.md).

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

## Roadmap

The project targets dependable non-motion secondary-MCU use rather than every
Klipper command. See [`ROADMAP.md`](ROADMAP.md) for the planned input, counter,
original ESP32 qualification, further ESP32-S3 validation, SPI, sensor, and
experimental single-extruder work.

## License

GNU GPLv3. See [`LICENSE`](LICENSE). See [`AUTHORS.md`](AUTHORS.md) for project
authorship and upstream provenance.
