#!/usr/bin/env python3
# Copyright (C) 2026 Justin Hayes <justinh@rahb.ca>
# Distributed under the terms of the GNU GPLv3 license.

"""Measure true serial round-trip latency over the Klipper binary protocol.

This exists to separate *transport* latency from any artifact of the packet
reader. It timestamps the first response byte and the fully parsed reply
independently, and runs a back-to-back burst so a single shared delay
(pipeline latency) can be told apart from per-command firmware work.

Reads are one-byte-first (see probe_mcu.read_packet): the read returns the
instant a reply byte arrives instead of waiting out a fixed-size/timeout read,
so the measured RTT reflects the link, not the reader.
"""

import argparse
import statistics
import sys
import time

import serial

import probe_mcu as pm

ACK = pm.msgproto.MESSAGE_MIN


def _drain_read(port, rb, deadline):
    """Block for the next byte (bounded by deadline), then drain the burst.
    Returns the monotonic time the first byte was seen, or None on timeout."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None
    port.timeout = remaining
    b = port.read(1)
    if not b:
        return None
    t = time.monotonic()
    rb.extend(b)
    waiting = port.in_waiting
    if waiting:
        rb.extend(port.read(waiting))
    return t


def timed_request(port, proto, seq, fmt, response_name, rb, timeout, **params):
    """Send one command and time the reply. Returns
    (decoded, seq, first_byte_s, full_s) where the times are seconds from
    immediately after the write completes. ACK and unrelated frames are skipped.
    """
    cmd = proto.lookup_command(fmt)
    port.write(pm.frame(proto, seq, cmd.encode_by_name(**params)))
    port.flush()
    t0 = time.monotonic()
    seq = (seq + 1) & pm.msgproto.MESSAGE_SEQ_MASK
    deadline = t0 + timeout
    t_first = None

    while True:
        while rb:
            n = proto.check_packet(rb)
            if n < 0:
                del rb[0]
                continue
            if n == 0:
                break  # incomplete frame; read more
            pkt = bytes(rb[:n])
            del rb[:n]
            if len(pkt) == ACK:
                continue  # bare acknowledgement
            decoded = proto.parse(pkt)
            if decoded["#name"] == response_name:
                return decoded, seq, (t_first - t0), (time.monotonic() - t0)
            # stats or an unrelated reply: ignore and keep parsing
        seen = _drain_read(port, rb, deadline)
        if seen is None:
            raise TimeoutError(f"no {response_name} within {timeout}s")
        if t_first is None:
            t_first = seen


def burst_test(port, proto, seq, rb, count, timeout):
    """Write `count` get_clock commands back-to-back, then collect every reply,
    recording each arrival relative to the end of the write burst.

    If all replies bunch just after one delay, that delay is a fixed pipeline
    latency (transport), not per-command firmware time. If they arrive spread
    apart, each command paid its own cost.
    """
    cmd = proto.lookup_command("get_clock")
    for _ in range(count):
        port.write(pm.frame(proto, seq, cmd.encode_by_name()))
        seq = (seq + 1) & pm.msgproto.MESSAGE_SEQ_MASK
    port.flush()
    t0 = time.monotonic()
    deadline = t0 + timeout
    arrivals = []

    while len(arrivals) < count:
        while rb:
            n = proto.check_packet(rb)
            if n < 0:
                del rb[0]
                continue
            if n == 0:
                break
            pkt = bytes(rb[:n])
            del rb[:n]
            if len(pkt) == ACK:
                continue
            decoded = proto.parse(pkt)
            if decoded["#name"] == "clock":
                arrivals.append(time.monotonic() - t0)
        if _drain_read(port, rb, deadline) is None:
            break
    return arrivals, seq


def _summary(name, samples_ms):
    s = sorted(samples_ms)
    n = len(s)
    p = lambda q: s[min(n - 1, int(q * n))]
    return (f"{name}: n={n} min={s[0]:.1f} median={statistics.median(s):.1f} "
            f"p90={p(0.9):.1f} max={s[-1]:.1f} ms")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("device")
    ap.add_argument("--baud", type=int, default=250_000)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--open-delay", type=float, default=1.0)
    ap.add_argument("--samples", type=int, default=50)
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--burst", type=int, default=8)
    args = ap.parse_args()

    port = serial.Serial(baudrate=args.baud, timeout=0.05, exclusive=True, port=None)
    port.dtr = False
    port.rts = False
    port.port = args.device
    with port:
        time.sleep(args.open_delay)
        port.reset_input_buffer()
        rb = bytearray()
        raw, seq = pm.identify(port, args.timeout, rb)
        proto = pm.msgproto.MessageParser()
        proto.process_identify(raw)
        print(f"identified MCU; measuring RTT over {args.device} @ {args.baud} baud")

        first_ms, full_ms = [], []
        for i in range(args.samples + args.warmup):
            _, seq, first_s, full_s = timed_request(
                port, proto, seq, "get_clock", "clock", rb, args.timeout)
            if i >= args.warmup:
                first_ms.append(first_s * 1e3)
                full_ms.append(full_s * 1e3)
            time.sleep(0.02)  # let the link settle between samples

        print("\n-- round-trip latency (single get_clock) --")
        print("  " + _summary("first-byte", first_ms))
        print("  " + _summary("full-reply", full_ms))

        arrivals, seq = burst_test(port, proto, seq, rb, args.burst, args.timeout)
        print(f"\n-- burst: {args.burst} get_clock written back-to-back --")
        if arrivals:
            arr_ms = [a * 1e3 for a in arrivals]
            spread = arr_ms[-1] - arr_ms[0]
            print(f"  replies received: {len(arrivals)}/{args.burst}")
            print(f"  first arrival: {arr_ms[0]:.1f} ms  last: {arr_ms[-1]:.1f} ms  "
                  f"spread: {spread:.1f} ms")
            verdict = ("shared pipeline delay (transport)" if spread < arr_ms[0]
                       else "per-command cost")
            print(f"  interpretation: {verdict}")
        else:
            print("  no replies — burst FAILED")
            sys.exit(1)

        if not full_ms:
            print("no RTT samples collected — FAILED")
            sys.exit(1)


if __name__ == "__main__":
    main()
