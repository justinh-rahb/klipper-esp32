# Panda Breath (ESP32-C3) hardware bring-up report

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
- ❌ Still not `Ready`: under continuous traffic the link degrades into a retransmit / `bytes_invalid` storm (`srtt≈70 ms`, `rttvar≈39 ms`, `rto` saturates) and Klippy eventually loses communication.

**Isolated to the CH340 chip's UART→USB buffering — not the host, not the firmware.** Ruled out step by step:
- MCU clock proven correct: 71-min rollover soak + 66-sample rapid poll, 0 anomalies.
- **Firmware exonerated by a burst test:** 8 `get_clock`s written back-to-back (0.2 ms) return with all 8 replies bunched within ~5 ms *after* one shared ~78 ms delay — so the delay is a fixed pipeline latency, not per-command firmware work. (FreeRTOS tick 1 kHz, `irq_wait` ≤5 ms, `console_io_task` polls UART every loop.)
- **Measured true RTT over CH340 @ 250 k (`tools/latency_probe.py`, one-byte-first reader): ~80 ms, ~1 ms jitter, unimodal.** An earlier "bimodal 45/90 ms" reading was a packet-reader artifact — the old reader did a fixed `read(256)` under a 50 ms per-read timeout, quantizing the true ~80 ms latency into ~50 ms buckets. The corrected reader (`tools/probe_mcu.py`, buffered-first / one-byte-first) removes that and shows a consistent ~80 ms.
- **Under real Klippy load the link collapses:** `srtt≈70 ms`, `rttvar≈39 ms`, `rto` saturates at 5 s, `receive_seq` stalls, and `bytes_retransmit` / `bytes_invalid` climb steadily until the host declares "Lost communication". The `bytes_invalid` is a *symptom* of the retransmit storm (overlapping/duplicated frames desync the parser), not independent corruption — the ~80 ms RTT exceeds Klipper's clock-sync RTO during the initial handshake, so it retransmits before replies arrive and never converges.
- **Baud is not the cause:** rebuilt and retested at **115200** — RTT unchanged (~79.5 ms) and real Klippy fails identically (`srtt≈71 ms`, same retransmit/`bytes_invalid` storm, never `Ready`). The ~80 ms delay is fixed CH340 buffering, independent of serialization rate, so lowering the baud does not help.
- Ruled out on the host/link side: USB extension cable removed (no change), a different USB port on the same host (no change), a second USB cable (no change), serial `ASYNC_LOW_LATENCY` (no effect; ch341 exposes no `latency_timer`), USB autosuspend (already disabled), realtime Linux primary `-r` (no change), lower baud (115200, no change).
- **Different host ruled out:** re-ran the probe from the printer's own host — an RK3562 with a different `ch341` driver and USB stack — and measured **identically** (first-byte 78.9–79.9 ms, median 79.3). The latency is host-independent.
- **Firmware ruled out (both directions):** minimizing the ESP-IDF UART RX path (`uart_set_rx_full_threshold(1)` + `uart_set_rx_timeout(1)`) changed nothing, and making TX unbuffered (`tx_buffer_size=0`, direct-to-FIFO) changed nothing — so neither RX FIFO batching nor the TX ring handoff is the source. The `console_io_task` loop was also verified fast (`irq_wait` wakes every ≤5 ms).
- **Klipper `MIN_RTO`:** raising the retransmit-timeout floor above the link RTT (`MIN_RTO` 25 → 150 ms in `chelper/serialqueue.c`) *eliminated* the initial retransmit / `bytes_invalid` storm — proving that storm was a **symptom** of premature retransmits, not the root cause. With it gone, the primary role still diverges (freq runaway) and the secondary role reaches the **correct frequency (~998 kHz)** but is then defeated by **±40 ms clock-sample jitter under load**, which trips the estimator's outlier reset (`Resetting prediction variance`) endlessly. This matches Klipper community reports of network/`ser2net` serial links failing to reach `Ready`.
- **Conclusion:** with host (including a completely different machine), cables, USB port, baud, RX threshold/timeout, TX buffering, and the retransmit timeout all eliminated with no effect, the fixed ~80 ms is the **CH340 chip's UART→USB return-path buffering**. A logic analyzer on the C3 TX pin would only confirm it.

**Architectural constraint:** the panda is locked to CH340 UART — on the C3, native USB Serial/JTAG (low latency, the path the README validated as a Klippy secondary) is on GPIO18/19, and **GPIO18 is the heater relay**. So the panda cannot use native USB.

**Implication for the project:** every Klipper protocol operation works over CH340 UART, but the chip's fixed ~80 ms return-path latency prevents Klipper clock-sync from reaching `Ready` in either role. Since it's the CH340 chip — not the host, cabling, baud, or firmware, all tested — the only fixes are a **different bridge chip** or **native USB Serial/JTAG**, and native USB is unavailable on this board (it's on GPIO18/19 and GPIO18 is the heater relay). ESP32 over native USB is fine (the `dev`/S3 profiles use it); the **CH340 UART bridge specifically is unsuitable for a live Klipper MCU**. The board remains fully usable for one-shot protocol operations (ADC, digital out, the safety lockout) — just not as a clock-synced MCU.

## Not applicable to the panda profile (absent from its 17-command dictionary)
- RMT NeoPixel (dev-profile feature; panda has plain-GPIO LEDs, no addressable LED).
- LEDC hardware PWM / hardware I2C (bentobox-profile features).
- Panda fan is TRIAC phase-angle on GPIO3 (AC) — intentionally never driven in bench testing.

## Test harnesses
- [`tools/hw_test.py`](../tools/hw_test.py) — digital-out, ADC, and heater-lockout tests over the Klipper protocol.
- [`tools/latency_probe.py`](../tools/latency_probe.py) — first-byte/full-reply RTT and back-to-back burst timing.
- [`tools/reconnect_test.py`](../tools/reconnect_test.py) — USB disconnect/reconnect recovery via kernel `authorized`.
- [`tools/rollover_soak.py`](../tools/rollover_soak.py) — continuous-session 32-bit rollover soak with post-rollover functional check.
- [`tools/run_klippy_test.py`](../tools/run_klippy_test.py) with [`config/dev-panda-klippy.cfg`](../config/dev-panda-klippy.cfg) or [`config/dev-panda-secondary.cfg`](../config/dev-panda-secondary.cfg) — real Klippy host connection tests (heater-free).
