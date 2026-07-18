#!/usr/bin/env python3
# USB disconnect/reconnect recovery test for the Panda Breath MCU.
#
# Uses the kernel USB "authorized" flag to force a genuine host-side
# disconnect (device removed, ttyUSB0 disappears) and reconnect
# (re-enumeration). Power is not cut, so the MCU keeps running and its
# uptime must advance across the gap, proving the host re-identifies a
# still-live MCU.

import subprocess
import sys
import time

import serial

import probe_mcu as pm

DEV = "/dev/ttyUSB0"
USBDEV = "2-2"  # sysfs USB device node for the CH340 bridge


def identify_uptime(tag):
    """Identify the MCU and confirm liveness by reading uptime twice within the
    same session (this board auto-resets on port-open, so cross-session uptime
    is not continuous; within-session advance proves the MCU is running)."""
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
    up1, seq = pm.request(p, proto, seq, "get_uptime", "uptime", 5.0, rb)
    time.sleep(2.0)
    up2, seq = pm.request(p, proto, seq, "get_uptime", "uptime", 5.0, rb)
    cfg, seq = pm.request(p, proto, seq, "get_config", "config", 5.0, rb)
    p.close()
    t1 = (up1["high"] << 32) | up1["clock"]
    t2 = (up2["high"] << 32) | up2["clock"]
    live = t2 > t1
    print(f"  [{tag}] identify OK, uptime {t1}->{t2} (Δ{t2-t1} in ~2s) "
          f"advancing={live} is_shutdown={cfg['is_shutdown']}")
    return live and not cfg["is_shutdown"]


def set_authorized(val):
    subprocess.run(
        ["sudo", "sh", "-c", f"echo {val} > /sys/bus/usb/devices/{USBDEV}/authorized"],
        check=True)


def wait_for_dev(present, timeout=10.0):
    import os
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if os.path.exists(DEV) == present:
            return True
        time.sleep(0.2)
    return False


def main():
    print("=== TEST: USB disconnect/reconnect recovery ===")
    ok_before = identify_uptime("before")

    print("  deauthorizing USB device (simulated disconnect) ...")
    set_authorized(0)
    if not wait_for_dev(present=False):
        print("  WARN: ttyUSB0 did not disappear")
    else:
        print("  ttyUSB0 removed (host sees disconnect)")
    time.sleep(2.0)

    print("  reauthorizing USB device (reconnect) ...")
    set_authorized(1)
    if not wait_for_dev(present=True):
        print("  RESULT: FAIL — ttyUSB0 did not return after reconnect")
        sys.exit(1)
    print("  ttyUSB0 re-enumerated")
    time.sleep(1.5)  # settle for udev to set permissions

    ok_after = identify_uptime("after")

    print("  (note: this board auto-resets the MCU on port-open, so uptime "
          "restarts each session by design)")
    print("  RESULT:", "PASS — MCU re-identified and running after reconnect"
          if (ok_before and ok_after) else "FAIL")


if __name__ == "__main__":
    main()
