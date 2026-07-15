#!/usr/bin/env python3
# Copyright (C) 2026 Justin Hayes <justinh@rahb.ca>
# Distributed under the terms of the GNU GPLv3 license.

"""Validate the minimal Klipper MCU dictionary emitted by the build."""

import argparse
import json
from pathlib import Path


REQUIRED_COMMANDS = {
    "allocate_oids count=%c",
    "config_analog_in oid=%c pin=%u",
    "config_digital_out oid=%c pin=%u value=%c default_value=%c max_duration=%u",
    "config_reset",
    "emergency_stop",
    "finalize_config crc=%u",
    "get_clock",
    "get_config",
    "get_uptime",
    "identify offset=%u count=%c",
    "query_analog_in oid=%c clock=%u sample_ticks=%u sample_count=%c rest_ticks=%u min_value=%hu max_value=%hu range_check_count=%c",
    "queue_digital_out oid=%c clock=%u on_ticks=%u",
    "reset",
    "set_digital_out_pwm_cycle oid=%c cycle_ticks=%u",
    "update_digital_out oid=%c value=%c",
}

REQUIRED_RESPONSES = {
    "analog_in_state oid=%c next_clock=%u value=%hu",
    "clock clock=%u",
    "config is_config=%c crc=%u is_shutdown=%c move_count=%hu",
    "identify_response offset=%u data=%.*s",
    "shutdown clock=%u static_string_id=%hu",
    "uptime high=%u clock=%u",
}

DEV_NEOPIXEL_COMMANDS = {
    "config_neopixel oid=%c pin=%u data_size=%hu bit_max_ticks=%u reset_min_ticks=%u",
    "neopixel_send oid=%c",
    "neopixel_update oid=%c pos=%hu data=%*s",
}

BENTOBOX_COMMANDS = {
    "config_i2c oid=%c",
    "config_pwm_out oid=%c pin=%u cycle_ticks=%u value=%hu default_value=%hu max_duration=%u",
    "i2c_read oid=%c reg=%*s read_len=%u",
    "i2c_set_bus oid=%c i2c_bus=%u rate=%u address=%u",
    "i2c_write oid=%c data=%*s",
    "queue_pwm_out oid=%c clock=%u value=%hu",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "dictionary",
        nargs="?",
        type=Path,
        default=Path("build-dev/esp-idf/klipper/klipper.dict"),
    )
    parser.add_argument("--profile", choices=("dev", "panda", "bentobox"))
    args = parser.parse_args()

    with args.dictionary.open(encoding="utf-8") as stream:
        dictionary = json.load(stream)

    config = dictionary.get("config", {})
    expected_config = {
        "ADC_MAX": 4095,
        "CLOCK_FREQ": 1_000_000,
        "MCU": "esp32c3",
        "SERIAL_BAUD": 250_000,
    }
    for key, expected in expected_config.items():
        actual = config.get(key)
        if actual != expected:
            raise SystemExit(f"{key}: expected {expected!r}, got {actual!r}")

    commands = set(dictionary.get("commands", {}))
    missing_commands = sorted(REQUIRED_COMMANDS - commands)
    if missing_commands:
        raise SystemExit(f"missing commands: {missing_commands}")

    responses = set(dictionary.get("responses", {}))
    missing_responses = sorted(REQUIRED_RESPONSES - responses)
    if missing_responses:
        raise SystemExit(f"missing responses: {missing_responses}")

    static_strings = dictionary.get("enumerations", {}).get(
        "static_string_id", {}
    )
    lockout = "Panda heater safety interlocks not armed"
    if args.profile == "panda" and lockout not in static_strings:
        raise SystemExit("panda profile is missing the heater safety lockout")
    if args.profile in ("dev", "bentobox") and lockout in static_strings:
        raise SystemExit(
            f"{args.profile} profile unexpectedly contains Panda hardware code"
        )
    if args.profile == "dev":
        missing_neopixel = sorted(DEV_NEOPIXEL_COMMANDS - commands)
        if missing_neopixel:
            raise SystemExit(f"dev profile is missing NeoPixel commands: {missing_neopixel}")
        if "neopixel_result oid=%c success=%c" not in responses:
            raise SystemExit("dev profile is missing the NeoPixel response")
    if args.profile == "panda" and DEV_NEOPIXEL_COMMANDS & commands:
        raise SystemExit("panda profile unexpectedly contains NeoPixel commands")
    if args.profile == "bentobox":
        missing_bentobox = sorted(BENTOBOX_COMMANDS - commands)
        if missing_bentobox:
            raise SystemExit(
                f"bentobox profile is missing commands: {missing_bentobox}"
            )
        if "i2c_read_response oid=%c response=%*s" not in responses:
            raise SystemExit("bentobox profile is missing the I2C response")
        if config.get("BUS_PINS_i2c0") != "GPIO_NUM_4,GPIO_NUM_5":
            raise SystemExit("bentobox profile has the wrong I2C pins")
        if config.get("PWM_MAX") != 1023:
            raise SystemExit("bentobox profile has the wrong PWM range")
        i2c_buses = dictionary.get("enumerations", {}).get("i2c_bus", {})
        if i2c_buses.get("i2c0") != 0:
            raise SystemExit("bentobox profile is missing hardware I2C bus i2c0")

    print(
        f"validated {args.dictionary}: "
        f"{len(commands)} commands, {len(responses)} responses"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
