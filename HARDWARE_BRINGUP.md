# Panda Breath (ESP32-C3) hardware bring-up — results

Date: 2026-07-18. Rig: BIQU Panda Breath board on `/dev/ttyUSB0`, tested by Claude.

## Hardware identified
- Chip: **ESP32-C3** (rev v1.1), 4 MB embedded flash, MAC `ac:eb:e6:8f:e5:1c`.
- Bridge: **CH340** USB-UART (`1a86:USB Serial`); Klipper transport UART0 @ 250000 baud.
- Board auto-resets the MCU on serial port open (normal for UART-bridge ESP32; MCU uptime restarts each host session by design).

## Firmware
- Built from this repo: `./build.sh panda` (ESP-IDF **v5.3.5**). Image `klipper_esp32c3.bin` (177 KB).
- Dictionary validated: **17 commands, 9 responses**; `MCU=esp32c3 CLOCK_FREQ=1000000 SERIAL_BAUD=250000 ADC_MAX=4095`.
- Stock OEM `panda_breath` firmware (WiFi-enabled, ESP-IDF 5.1.4) backed up to `~/panda_breath_stock_backup_acebe68fe51c.bin` (sha256 6f9dd62c…) before flashing.
- New firmware flashed and hash-verified via esptool (CH340 auto-reset; no manual BOOT/RESET).

## Test results — 7/7 device tests PASS
| # | Test | Result | Evidence |
|---|------|--------|----------|
| 1 | Identify / clock / uptime / config / watchdog-stability | ✅ PASS | uptime advancing Δ6.30M ticks/6.3 s; is_config/shutdown correct |
| 2 | Scheduled + immediate digital output (LEDs GPIO4/5/6) | ✅ PASS | config+finalize is_config=1; immediate blink; queue_digital_out ON/OFF at MCU clock; no shutdown |
| 3 | ADC read TH0 (GPIO0 / ADC1_CH0) | ✅ PASS | sum 19652 → avg 2456/4095 ≈ 1.98 V |
| 4 | ADC read TH1 (GPIO1 / ADC1_CH1) | ✅ PASS | sum 19918 → avg 2490/4095 ≈ 2.01 V |
| 5 | Heater relay lockout (GPIO18 → shutdown) | ✅ PASS | GPIO18-high → shutdown `"Panda heater safety interlocks not armed"` (id 28) |
| 6 | USB disconnect/reconnect recovery | ✅ PASS | kernel `authorized` toggle removed+re-enumerated ttyUSB0; MCU re-identified, uptime advancing, not shutdown |
| 7 | 32-bit timer rollover soak (~71.6 min) | ✅ PASS | single continuous session; `high` 0→1 at t+71.68 min (low wrapped 4,289,404,830→9,737,534), shutdown=0 throughout; post-rollover get_clock + LED drive succeeded |

Independent clock health check: 66 rapid `get_clock` samples over 10 s → **0 monotonic anomalies**, rate ≈ 1 MHz.

## Klippy host connection — full stack runs; clock-sync blocked by CH340 UART latency
Ran a real Klippy host (venv; `chelper` compiled) in two roles. **GPIO18 never configured** in either.

**Primary role** (ESP32 as `[mcu]`): connects, loads dict, `Configured MCU (1024 moves)`, but the primary clock-sync estimator **diverges** (runaway ~2³² diff after config) → never `Ready`.

**Secondary role** (Klipper Linux host-MCU built as primary `[mcu]`; ESP32 as `[mcu panda]`):
- ✅ Both MCUs connect and configure (`Configured MCU 'mcu'` + `Configured MCU 'panda' (1024 moves)`).
- ✅ Panda clock **frequency syncs correctly** (freq → 1,000,204 Hz, ~0.02% — no divergence, unlike primary role).
- ✅ **Panda ADC data flows to the host** (`analog_in_state` values received for both channels).
- ❌ Still not `Ready`: clock-sync residual holds a ~±30–50 ms sawtooth (variance never settles).

**Root cause = a fixed ~45 ms latency in the CH340 UART transport, not firmware.** Ruled out step by step:
- MCU clock proven correct: 71-min rollover soak + 66-sample rapid poll, 0 anomalies.
- **Firmware exonerated by a burst test:** 8 `get_clock`s written back-to-back (0.2 ms) return with all 8 replies bunched within ~5 ms *after* one shared ~45 ms delay — so the delay is a fixed pipeline latency, not per-command firmware work. (FreeRTOS tick 1 kHz, `irq_wait` ≤5 ms, `console_io_task` polls UART every loop.)
- Measured true RTT over CH340 @ 250 k: **~90 ms median, ~45 ms floor, ~30–45 ms jitter** (bimodal 45/90 ms ⇒ a ~45 ms periodic return-path flush).
- Ruled out on the host/link side: USB extension cable removed (no change), a different USB port on the same host (no change), serial `ASYNC_LOW_LATENCY` (no effect; ch341 exposes no `latency_timer`), USB autosuspend (already disabled, device stays active), realtime Linux primary `-r` (no change). Only a different bridge chip or host machine remains untested.

**Architectural constraint:** the panda is locked to CH340 UART — on the C3, native USB Serial/JTAG (low latency, the path the README validated as a Klippy secondary) is on GPIO18/19, and **GPIO18 is the heater relay**. So the panda cannot use native USB.

**Implication for the project:** every Klipper protocol operation works over CH340 UART, but the transport's ~90 ms latency/jitter prevents Klipper clock-sync from reaching `Ready` in both roles. Getting the panda usable as a live Klipper MCU needs the CH340 link latency reduced (CH340 driver/latency-timer investigation, a different bridge, or host/port changes) — worth raising in the PR.

## Not applicable to the panda profile (absent from its 17-command dictionary)
- RMT NeoPixel (dev-profile feature; panda has plain-GPIO LEDs, no addressable LED).
- LEDC hardware PWM / hardware I2C (bentobox-profile features).
- Panda fan is TRIAC phase-angle on GPIO3 (AC) — intentionally never driven in bench testing.

## Repo issues found (for the PR)
1. `config/panda-breath.cfg` uses `sensor_type: NTC 100K beta 3950`, which is **not a defined sensor type** in this Klipper fork (built-ins include `Generic 3950`, `EPCOS 100K B57560G104F`, …). Would fail against a real Klippy as written.
2. **CH340 UART transport latency (~90 ms, ~30–45 ms jitter) blocks Klipper clock-sync from reaching `Ready`** — in both primary and secondary roles — even though all protocol ops work. The MCU clock is provably correct; the bottleneck is the bridge link. This is the key blocker for using the panda as a live Klipper MCU and needs investigation (CH340 latency-timer, host/port, or transport change). Native USB is unavailable (GPIO18 = relay).

## Test harnesses added (candidates for the PR)
- `hw_test.py` — digital-out, ADC, and heater-lockout tests over the Klipper protocol.
- `reconnect_test.py` — USB disconnect/reconnect recovery via kernel `authorized`.
- `rollover_soak.py` — continuous-session 32-bit rollover soak with post-rollover functional check.
- `run_klippy_test.py` + `panda_connect.cfg` — real Klippy host connection test (heater-free).
