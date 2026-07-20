#!/usr/bin/env python3
# Panda Breath (ESP32-C3) hardware qualification harness.
#
# Exercises the remaining validation items over the Klipper binary protocol
# without a full Klippy host: scheduled digital output on the button LEDs,
# ADC reads on the two thermistor channels, and the heater-relay safety
# lockout. Deliberately never drives GPIO3 (TRIAC/AC fan) and only drives
# GPIO18 (heater relay) in the dedicated lockout test, which expects a shutdown.
#
# Reuses the low-level framing helpers from tools/probe_mcu.py.

import argparse
import json
import sys
import time
import zlib

import serial

import probe_mcu as pm

# Panda Breath confirmed-safe pins (see board_profiles/panda_breath/pins.h)
LED_K1 = "GPIO_NUM_6"
LED_K2 = "GPIO_NUM_5"
LED_K3 = "GPIO_NUM_4"
NTC_CHAMBER = "GPIO_NUM_0"   # ADC1_CH0 (TH0)
NTC_PTC = "GPIO_NUM_1"       # ADC1_CH1 (TH1)
RELAY = "GPIO_NUM_18"        # heater relay, locked off


def reset_mcu(device, baud, open_delay, timeout):
    """Send the Klipper `reset` command and let the MCU reboot to a clean,
    unconfigured state so a fresh allocate_oids/finalize sequence can run."""
    port = open_port(device, baud, open_delay)
    with port:
        proto, seq, rb, _ = identify(port, timeout)
        cmd = proto.lookup_command("reset")
        try:
            port.write(pm.frame(proto, seq, cmd.encode_by_name()))
            port.flush()
        except Exception:
            pass
    time.sleep(2.0)  # allow reboot


def open_port(device, baud, open_delay):
    port = serial.Serial(baudrate=baud, timeout=0.05, exclusive=True, port=None)
    port.dtr = False
    port.rts = False
    port.port = device
    port.open()
    time.sleep(open_delay)
    port.reset_input_buffer()
    return port


def wait_for(port, parser, name, timeout, rb):
    """Read frames until a response with the given #name arrives."""
    deadline = time.monotonic() + timeout
    while True:
        resp = pm.read_packet(port, parser, deadline, rb)
        if len(resp) == pm.msgproto.MESSAGE_MIN:
            continue
        decoded = parser.parse(resp)
        if decoded["#name"] == name:
            return decoded
        if decoded["#name"] in ("shutdown", "is_shutdown"):
            return decoded


def identify(port, timeout):
    rb = bytearray()
    raw, seq = pm.identify(port, timeout, rb)
    proto = pm.msgproto.MessageParser()
    proto.process_identify(raw)
    d = json.loads(zlib.decompress(raw))
    return proto, seq, rb, d


def get_clock(port, proto, seq, timeout, rb):
    dec, seq = pm.request(port, proto, seq, "get_clock", "clock", timeout, rb)
    return dec["clock"], seq


def test_digital(port, proto, seq, rb, freq, timeout):
    print("\n=== TEST: scheduled + immediate digital output (button LEDs) ===")
    # Allocate: oid0..2 = LEDs, oid3/4 = ADC channels
    seq = pm.send_command(port, proto, seq, "allocate_oids count=%c", timeout, rb, count=5)
    for oid, pin in ((0, LED_K1), (1, LED_K2), (2, LED_K3)):
        seq = pm.send_command(
            port, proto, seq,
            "config_digital_out oid=%c pin=%u value=%c default_value=%c max_duration=%u",
            timeout, rb, oid=oid, pin=pin, value=0, default_value=0, max_duration=0)
    seq = pm.send_command(port, proto, seq, "config_analog_in oid=%c pin=%u", timeout, rb,
                          oid=3, pin=NTC_CHAMBER)
    seq = pm.send_command(port, proto, seq, "config_analog_in oid=%c pin=%u", timeout, rb,
                          oid=4, pin=NTC_PTC)
    crc = zlib.crc32(b"panda-hw-test") & 0xffffffff
    seq = pm.send_command(port, proto, seq, "finalize_config crc=%u", timeout, rb, crc=crc)
    dec, seq = pm.request(port, proto, seq, "get_config", "config", timeout, rb)
    print(f"  finalize: is_config={dec['is_config']} crc={dec['crc']} "
          f"is_shutdown={dec['is_shutdown']} move_count={dec['move_count']}")
    if not (dec["is_config"] and not dec["is_shutdown"]):
        print("  RESULT: FAIL (config did not finalize cleanly)")
        return seq, False

    # Immediate blink of each LED (visible)
    print("  immediate update_digital_out blink K1,K2,K3 ...")
    for oid in (0, 1, 2):
        seq = pm.send_command(port, proto, seq, "update_digital_out oid=%c value=%c", timeout, rb,
                              oid=oid, value=1)
        time.sleep(0.35)
        seq = pm.send_command(port, proto, seq, "update_digital_out oid=%c value=%c", timeout, rb,
                              oid=oid, value=0)

    # Scheduled: LED_K1 ON at now+0.5s, OFF at now+1.0s (proves MCU-clock scheduling)
    now, seq = get_clock(port, proto, seq, timeout, rb)
    on_at = (now + freq // 2) & 0xffffffff
    off_at = (now + freq) & 0xffffffff
    seq = pm.send_command(port, proto, seq, "queue_digital_out oid=%c clock=%u on_ticks=%u", timeout, rb,
                          oid=0, clock=on_at, on_ticks=1)
    seq = pm.send_command(port, proto, seq, "queue_digital_out oid=%c clock=%u on_ticks=%u", timeout, rb,
                          oid=0, clock=off_at, on_ticks=0)
    print(f"  queued LED_K1 ON@{on_at} OFF@{off_at} (clock now={now})")
    time.sleep(1.5)
    # Confirm still alive and not shut down
    dec, seq = pm.request(port, proto, seq, "get_config", "config", timeout, rb)
    print(f"  post-schedule: is_config={dec['is_config']} is_shutdown={dec['is_shutdown']}")
    if dec["is_shutdown"]:
        print("  RESULT: FAIL (MCU shut down during scheduled digital output)")
        return seq, False
    print("  RESULT: PASS")
    return seq, True


def wait_for_adc(port, proto, oid, timeout, rb):
    """Wait for an analog_in_state for a specific oid (ignoring the other
    channel's reports); surface a shutdown if one occurs."""
    deadline = time.monotonic() + timeout
    while True:
        resp = pm.read_packet(port, proto, deadline, rb)
        if len(resp) == pm.msgproto.MESSAGE_MIN:
            continue
        dec = proto.parse(resp)
        if dec["#name"] == "analog_in_state" and dec.get("oid") == oid:
            return dec
        if dec["#name"] in ("shutdown", "is_shutdown"):
            return dec


def test_adc(port, proto, seq, rb, freq, timeout):
    print("\n=== TEST: ADC read on thermistor channels (GPIO0/GPIO1) ===")
    results = {}
    sample_count = 8
    # min/max are compared against the oversampled SUM (sample_count * reading);
    # 0..0xffff can never be violated by a valid 12-bit sum, so range checking
    # never trips. rest_ticks is set far out so each channel reports ~once
    # during the capture window instead of streaming continuously.
    for oid, name in ((3, "TH0/chamber GPIO0"), (4, "TH1/PTC GPIO1")):
        now, seq = get_clock(port, proto, seq, timeout, rb)
        cmd = proto.lookup_command(
            "query_analog_in oid=%c clock=%u sample_ticks=%u sample_count=%c "
            "rest_ticks=%u min_value=%hu max_value=%hu range_check_count=%c")
        payload = cmd.encode_by_name(
            oid=oid, clock=(now + freq // 5) & 0xffffffff, sample_ticks=1000,
            sample_count=sample_count, rest_ticks=freq * 30, min_value=0,
            max_value=0xffff, range_check_count=0)
        port.write(pm.frame(proto, seq, payload))  # fire-and-forget (ack piggybacks on stream)
        seq = (seq + 1) & pm.msgproto.MESSAGE_SEQ_MASK
        dec = wait_for_adc(port, proto, oid, timeout + 2.0, rb)
        if dec is None or dec.get("#name") != "analog_in_state":
            print(f"  {name}: no analog_in_state (got {dec})")
            continue
        summed = dec["value"]
        avg = summed / sample_count
        volts = avg / 4095.0 * 3.3
        results[oid] = avg
        print(f"  {name}: sum={summed} avg={avg:.1f}/4095  ~{volts:.3f} V (at 3.3V ref)")
    ok = len(results) == 2
    print("  RESULT:", "PASS" if ok else "PARTIAL")
    return seq, ok


def test_relay_lockout(device, baud, open_delay, timeout):
    print("\n=== TEST: heater relay lockout (GPIO18 -> expect shutdown) ===")
    port = open_port(device, baud, open_delay)
    with port:
        proto, seq, rb, _ = identify(port, timeout)
        seq = pm.send_command(port, proto, seq, "allocate_oids count=%c", timeout, rb, count=1)
        seq = pm.send_command(
            port, proto, seq,
            "config_digital_out oid=%c pin=%u value=%c default_value=%c max_duration=%u",
            timeout, rb, oid=0, pin=RELAY, value=0, default_value=0, max_duration=0)
        crc = zlib.crc32(b"panda-relay-test") & 0xffffffff
        seq = pm.send_command(port, proto, seq, "finalize_config crc=%u", timeout, rb, crc=crc)
        dec, seq = pm.request(port, proto, seq, "get_config", "config", timeout, rb)
        print(f"  finalize: is_config={dec['is_config']} is_shutdown={dec['is_shutdown']}")
        # Now attempt to energize the relay -> must latch shutdown
        cmd = proto.lookup_command("update_digital_out oid=%c value=%c")
        port.write(pm.frame(proto, seq, cmd.encode_by_name(oid=0, value=1)))
        dec = wait_for(port, proto, "shutdown", timeout, rb)
        sid = None
        if dec is not None and dec.get("#name") in ("shutdown", "is_shutdown"):
            sid = dec.get("static_string_id")
            # msgproto already maps the id to its string; handle both forms.
            if isinstance(sid, str):
                reason = sid
            else:
                enums = getattr(proto, "enumerations", {}).get("static_string_id", {})
                reason = next((k for k, v in enums.items() if v == sid), None)
            print(f"  GPIO18 high -> {dec['#name']} reason={reason!r}")
            ok = reason == "Panda heater safety interlocks not armed"
            print("  RESULT:", "PASS" if ok else f"UNEXPECTED (id={sid})")
            return ok
        print(f"  no shutdown observed (got {dec}) -> RESULT: FAIL (lockout not enforced!)")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("device")
    ap.add_argument("--baud", type=int, default=250000)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--open-delay", type=float, default=1.0)
    ap.add_argument("--skip-relay", action="store_true",
                    help="skip the heater lockout test (which leaves MCU shut down)")
    args = ap.parse_args()

    print("resetting MCU to a clean state ...")
    reset_mcu(args.device, args.baud, args.open_delay, args.timeout)

    results = []
    port = open_port(args.device, args.baud, args.open_delay)
    with port:
        proto, seq, rb, d = identify(port, args.timeout)
        freq = int(d["config"]["CLOCK_FREQ"])
        print(f"identified MCU={d['config'].get('MCU')} CLOCK_FREQ={freq} "
              f"commands={len(d.get('commands', {}))}")
        seq, ok = test_digital(port, proto, seq, rb, freq, args.timeout)
        results.append(("digital", ok))
        seq, ok = test_adc(port, proto, seq, rb, freq, args.timeout)
        results.append(("adc", ok))

    if not args.skip_relay:
        reset_mcu(args.device, args.baud, args.open_delay, args.timeout)
        ok = test_relay_lockout(args.device, args.baud, args.open_delay, args.timeout)
        results.append(("relay_lockout", ok))
        # Leave the MCU clean for any subsequent soak test
        reset_mcu(args.device, args.baud, args.open_delay, args.timeout)

    failed = [name for name, ok in results if not ok]
    print(f"\n=== SUMMARY: {len(results) - len(failed)}/{len(results)} passed ===")
    if failed:
        print("  FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
