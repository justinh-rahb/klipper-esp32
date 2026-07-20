#!/usr/bin/env python3
# 32-bit timer rollover soak for the Panda Breath MCU.
#
# Holds a single continuous Klipper session (the board auto-resets on
# port-open, so the session must NOT be reopened) and polls uptime until the
# low 32-bit clock wraps and the uptime `high` word increments 0 -> 1
# (~71.58 min at 1 MHz). At the boundary it runs a post-rollover functional
# check: config state, clock read, immediate LED drive, and a scheduled
# digital-out event whose clock lands after the wrap.

import json
import sys
import time
import zlib

import serial

import probe_mcu as pm

# Serial device: first CLI arg, else the common default.
DEV = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
LED = "GPIO_NUM_6"   # button-backlight LED, safe output
POLL = 15.0
MAX_SECONDS = 4900   # safety cap (~81 min)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    p = serial.Serial(baudrate=250000, timeout=0.05, exclusive=True, port=None)
    p.dtr = False
    p.rts = False
    p.port = DEV
    p.open()
    time.sleep(1.0)
    p.reset_input_buffer()
    rb = bytearray()
    raw, seq = pm.identify(p, 5.0, rb)
    proto = pm.msgproto.MessageParser()
    proto.process_identify(raw)
    dictionary = json.loads(zlib.decompress(raw))
    freq = int(dictionary["config"]["CLOCK_FREQ"])

    # Configure one LED so we can drive it before and after the rollover.
    seq = pm.send_command(p, proto, seq, "allocate_oids count=%c", 5.0, rb, count=1)
    seq = pm.send_command(
        p, proto, seq,
        "config_digital_out oid=%c pin=%u value=%c default_value=%c max_duration=%u",
        5.0, rb, oid=0, pin=LED, value=0, default_value=0, max_duration=0)
    seq = pm.send_command(p, proto, seq, "finalize_config crc=%u", 5.0, rb, crc=0xABCD1234)
    cfg, seq = pm.request(p, proto, seq, "get_config", "config", 5.0, rb)
    log(f"session up, configured is_config={cfg['is_config']} is_shutdown={cfg['is_shutdown']}")

    up, seq = pm.request(p, proto, seq, "get_uptime", "uptime", 5.0, rb)
    start_low = up["clock"]
    start_high = up["high"]
    eta = (0x100000000 - start_low) / freq
    log(f"start uptime high={start_high} low={start_low} (CLOCK_FREQ={freq}); "
        f"first rollover ETA ~{eta/60:.2f} min")

    t0 = time.monotonic()
    rolled = False
    rc = 1  # default: no clean rollover observed
    last_led = t0
    led_state = 0
    while True:
        elapsed = time.monotonic() - t0
        if elapsed > MAX_SECONDS:
            log("MAX_SECONDS reached without rollover — aborting")
            print("RESULT: INCOMPLETE", flush=True)
            rc = 2
            break

        up, seq = pm.request(p, proto, seq, "get_uptime", "uptime", 5.0, rb)
        cfg, seq = pm.request(p, proto, seq, "get_config", "config", 5.0, rb)
        high, low = up["high"], up["clock"]
        full = (high << 32) | low
        log(f"t+{elapsed/60:6.2f}min  high={high} low={low:>10} "
            f"uptime~{full/freq/60:6.2f}min shutdown={cfg['is_shutdown']}")

        if cfg["is_shutdown"]:
            log("MCU SHUTDOWN during soak!")
            print("RESULT: FAIL (shutdown during soak)", flush=True)
            rc = 1
            break

        if high > start_high and not rolled:
            rolled = True
            log(f"*** 32-BIT LOW-WORD ROLLOVER CROSSED (high {start_high}->{high}) ***")
            # Post-rollover functional check
            clk, seq = pm.request(p, proto, seq, "get_clock", "clock", 5.0, rb)
            now = clk["clock"]
            seq = pm.send_command(p, proto, seq, "update_digital_out oid=%c value=%c", 5.0, rb, oid=0, value=1)
            time.sleep(0.3)
            seq = pm.send_command(p, proto, seq, "update_digital_out oid=%c value=%c", 5.0, rb, oid=0, value=0)
            seq = pm.send_command(p, proto, seq, "queue_digital_out oid=%c clock=%u on_ticks=%u",
                                  5.0, rb, oid=0, clock=(now + freq // 2) & 0xffffffff, on_ticks=1)
            seq = pm.send_command(p, proto, seq, "queue_digital_out oid=%c clock=%u on_ticks=%u",
                                  5.0, rb, oid=0, clock=(now + freq) & 0xffffffff, on_ticks=0)
            time.sleep(1.2)
            cfg2, seq = pm.request(p, proto, seq, "get_config", "config", 5.0, rb)
            ok = not cfg2["is_shutdown"]
            rc = 0 if ok else 1
            log(f"post-rollover functional check: LED driven + scheduled event, "
                f"is_shutdown={cfg2['is_shutdown']}")
            log("RESULT: PASS — MCU stayed connected across the 32-bit rollover "
                "and accepted post-rollover commands" if ok else "RESULT: FAIL")
            # Continue briefly to show continued operation, then finish.
            time.sleep(20)
            up, seq = pm.request(p, proto, seq, "get_uptime", "uptime", 5.0, rb)
            log(f"post-rollover uptime high={up['high']} low={up['clock']} (still advancing)")
            break

        # keep-alive LED heartbeat every ~5 min (visible liveness)
        if time.monotonic() - last_led > 300:
            led_state ^= 1
            seq = pm.send_command(p, proto, seq, "update_digital_out oid=%c value=%c",
                                  5.0, rb, oid=0, value=led_state)
            last_led = time.monotonic()

        time.sleep(POLL)

    p.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
