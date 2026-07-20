#!/usr/bin/env python3
# Copyright (C) 2026 Justin Hayes <justinh@rahb.ca>
# Distributed under the terms of the GNU GPLv3 license.

"""Perform a minimal Klipper identify exchange over a serial device.

This deliberately avoids Klipper's Linux-only host C helper so an ESP32
development image can be smoke-tested from macOS.
"""

import argparse
import json
from pathlib import Path
import sys
import time

import serial


REPO_ROOT = Path(__file__).resolve().parent.parent
KLIPPER_KLIPPY = REPO_ROOT / "components" / "klipper" / "klipper" / "klippy"
sys.path.insert(0, str(KLIPPER_KLIPPY))
import msgproto  # noqa: E402


def read_packet(port, parser, deadline, data):
    # Parse buffered bytes first, then block only for the *next* byte and drain
    # whatever else has already arrived. Reading a fixed block (read(256)) under
    # a per-read timeout would wait out that timeout whenever a reply is shorter
    # than the block, inflating any latency measured on top of this reader; a
    # one-byte-first read returns as soon as the reply actually arrives.
    while True:
        # 1. Return a packet already sitting in the buffer without touching the
        #    port. Klipper's five-second stats message can share a read with a
        #    requested reply, so any trailing frame stays buffered for next call.
        while data:
            packet_len = parser.check_packet(data)
            if packet_len > 0:
                packet = bytes(data[:packet_len])
                del data[:packet_len]
                return packet
            if packet_len < 0:
                del data[0]
                continue
            break  # incomplete frame; need more bytes

        # 2. Nothing complete buffered — wait for the next byte, bounded by the
        #    overall deadline so a stalled link still times out.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("timed out waiting for a valid Klipper packet")
        port.timeout = remaining
        chunk = port.read(1)
        if not chunk:
            continue  # read timed out at the deadline; loop re-checks and raises
        data.extend(chunk)

        # 3. Drain the rest of this burst without blocking (it already arrived).
        waiting = port.in_waiting
        if waiting:
            data.extend(port.read(waiting))


def identify(port, timeout, receive_buffer):
    parser = msgproto.MessageParser()
    command = parser.lookup_command("identify offset=%u count=%c")
    output = bytearray()
    sequence = 0
    deadline = time.monotonic() + timeout

    while True:
        payload = command.encode_by_name(offset=len(output), count=40)
        packet = parser.encode_msgblock(sequence, payload)
        # This pinned ESP32 Klipper fork retains an old msgproto helper that
        # returns the two CRC bytes as a nested list.
        if isinstance(packet[-2], list):
            packet = packet[:-2] + packet[-2] + packet[-1:]
        port.write(bytes(packet))

        while True:
            response = read_packet(port, parser, deadline, receive_buffer)
            # Empty packets are acknowledgements. The response packet follows.
            if len(response) == msgproto.MESSAGE_MIN:
                continue
            decoded = parser.parse(response)
            if decoded["#name"] == "identify_response":
                break

        if decoded["offset"] != len(output):
            raise RuntimeError(
                f"identify offset mismatch: expected {len(output)}, "
                f"received {decoded['offset']}"
            )
        chunk = decoded["data"]
        if not chunk:
            sequence = (sequence + 1) & msgproto.MESSAGE_SEQ_MASK
            return bytes(output), sequence
        output.extend(chunk)
        sequence = (sequence + 1) & msgproto.MESSAGE_SEQ_MASK


def frame(parser, sequence, payload):
    packet = parser.encode_msgblock(sequence, payload)
    if isinstance(packet[-2], list):
        packet = packet[:-2] + packet[-2] + packet[-1:]
    return bytes(packet)


def request(
    port,
    parser,
    sequence,
    command_format,
    response_name,
    timeout,
    receive_buffer,
    **params,
):
    command = parser.lookup_command(command_format)
    port.write(frame(parser, sequence, command.encode_by_name(**params)))

    deadline = time.monotonic() + timeout
    while True:
        response = read_packet(port, parser, deadline, receive_buffer)
        if len(response) == msgproto.MESSAGE_MIN:
            continue
        decoded = parser.parse(response)
        if decoded["#name"] == response_name:
            return decoded, (sequence + 1) & msgproto.MESSAGE_SEQ_MASK


def send_command(
    port,
    parser,
    sequence,
    command_format,
    timeout,
    receive_buffer,
    **params,
):
    command = parser.lookup_command(command_format)
    port.write(frame(parser, sequence, command.encode_by_name(**params)))
    deadline = time.monotonic() + timeout
    while True:
        response = read_packet(port, parser, deadline, receive_buffer)
        if len(response) == msgproto.MESSAGE_MIN:
            return (sequence + 1) & msgproto.MESSAGE_SEQ_MASK
        decoded = parser.parse(response)
        if decoded["#name"] in ("shutdown", "is_shutdown"):
            raise RuntimeError(f"MCU shutdown during command: {decoded}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("device")
    parser.add_argument("--baud", type=int, default=250_000)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--open-delay",
        type=float,
        default=1.0,
        help="seconds to allow a native-USB MCU to reboot after opening",
    )
    parser.add_argument(
        "--stability-seconds",
        type=float,
        default=6.0,
        help="idle interval before rechecking uptime and watchdog stability",
    )
    parser.add_argument(
        "--neopixel-pin",
        type=int,
        help="configure one GRB NeoPixel on this GPIO and set it violet",
    )
    args = parser.parse_args()

    # Native ESP32 USB uses DTR/RTS for reset and bootloader entry. Open
    # with both inactive so a protocol probe cannot hold the MCU in reset.
    port = serial.Serial(
        baudrate=args.baud, timeout=0.05, exclusive=True, port=None
    )
    port.dtr = False
    port.rts = False
    port.port = args.device
    with port:
        time.sleep(args.open_delay)
        port.reset_input_buffer()
        receive_buffer = bytearray()
        raw_dictionary, sequence = identify(
            port, args.timeout, receive_buffer
        )

        protocol = msgproto.MessageParser()
        protocol.process_identify(raw_dictionary)
        uptime, sequence = request(
            port, protocol, sequence, "get_uptime", "uptime", args.timeout,
            receive_buffer=receive_buffer,
        )
        clock, sequence = request(
            port, protocol, sequence, "get_clock", "clock", args.timeout,
            receive_buffer=receive_buffer,
        )
        runtime_config, sequence = request(
            port, protocol, sequence, "get_config", "config", args.timeout,
            receive_buffer=receive_buffer,
        )
        time.sleep(args.stability_seconds)
        later_uptime, sequence = request(
            port, protocol, sequence, "get_uptime", "uptime", args.timeout,
            receive_buffer=receive_buffer,
        )
        neopixel_result = None
        if args.neopixel_pin is not None:
            sequence = send_command(
                port,
                protocol,
                sequence,
                "allocate_oids count=%c",
                args.timeout,
                receive_buffer=receive_buffer,
                count=1,
            )
            sequence = send_command(
                port,
                protocol,
                sequence,
                "config_neopixel oid=%c pin=%u data_size=%hu bit_max_ticks=%u reset_min_ticks=%u",
                args.timeout,
                receive_buffer=receive_buffer,
                oid=0,
                pin=f"GPIO_NUM_{args.neopixel_pin}",
                data_size=3,
                bit_max_ticks=4,
                reset_min_ticks=50,
            )
            sequence = send_command(
                port,
                protocol,
                sequence,
                "finalize_config crc=%u",
                args.timeout,
                receive_buffer=receive_buffer,
                crc=0xC3C3C3C3,
            )
            sequence = send_command(
                port,
                protocol,
                sequence,
                "neopixel_update oid=%c pos=%hu data=%*s",
                args.timeout,
                receive_buffer=receive_buffer,
                oid=0,
                pos=0,
                data=bytes((0, 32, 32)),  # GRB: low-brightness violet
            )
            neopixel_result, sequence = request(
                port,
                protocol,
                sequence,
                "neopixel_send oid=%c",
                "neopixel_result",
                args.timeout,
                receive_buffer=receive_buffer,
                oid=0,
            )

    dictionary = json.loads(__import__("zlib").decompress(raw_dictionary))
    constants = dictionary.get("config", {})
    print(
        "Klipper MCU identified: "
        f"MCU={constants.get('MCU')} CLOCK_FREQ={constants.get('CLOCK_FREQ')} "
        f"SERIAL_BAUD={constants.get('SERIAL_BAUD')}"
    )
    print(
        f"dictionary: {len(raw_dictionary)} compressed bytes, "
        f"{len(dictionary.get('commands', {}))} commands, "
        f"{len(dictionary.get('responses', {}))} responses"
    )
    full_uptime = (uptime["high"] << 32) | uptime["clock"]
    later_full_uptime = (
        (later_uptime["high"] << 32) | later_uptime["clock"]
    )
    elapsed_ticks = later_full_uptime - full_uptime
    minimum_ticks = args.stability_seconds * int(constants["CLOCK_FREQ"]) * 0.8
    if elapsed_ticks < minimum_ticks:
        raise SystemExit(
            f"MCU uptime did not advance across stability interval: {elapsed_ticks} ticks"
        )
    print(
        f"runtime: uptime_ticks={full_uptime} clock={clock['clock']} "
        f"configured={bool(runtime_config['is_config'])} "
        f"shutdown={bool(runtime_config['is_shutdown'])} "
        f"stability_delta_ticks={elapsed_ticks}"
    )
    if neopixel_result is not None:
        if not neopixel_result["success"]:
            raise SystemExit("NeoPixel RMT transmission failed")
        print(f"neopixel: GPIO{args.neopixel_pin} RMT transmission succeeded")


if __name__ == "__main__":
    main()
