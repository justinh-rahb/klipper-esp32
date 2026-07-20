#!/usr/bin/env python3
# USB re-enumeration / reboot-recovery test for the Panda Breath MCU.
#
# Uses the kernel USB "authorized" flag to force a genuine host-side
# disconnect (the device is removed and its ttyUSB node disappears) and then a
# reconnect (re-enumeration). This proves the host cleanly re-enumerates the
# bridge and re-identifies the MCU afterward.
#
# It does NOT prove the MCU stayed alive across the gap: this board auto-resets
# the MCU whenever the serial port is opened, so every identify starts a fresh
# MCU session. Uptime is therefore only checked *within* a session (it must
# advance) to confirm the re-identified MCU is actually running — cross-session
# uptime is not continuous by design.

import glob
import os
import subprocess
import sys
import time

import serial

import probe_mcu as pm

CH340_VENDOR = "1a86"


def resolve_ch340(dev=None):
    """Locate the CH340 serial port and its sysfs USB device node.

    Returns (tty_path, usb_node) e.g. ("/dev/ttyUSB0", "2-2"). Verifies the
    bridge really is a CH340 (idVendor 1a86) rather than assuming a fixed node.
    """
    candidates = [dev] if dev else sorted(glob.glob("/dev/ttyUSB*"))
    for tty in candidates:
        if not tty or not os.path.exists(tty):
            continue
        node = os.path.realpath("/sys/class/tty/%s/device" % os.path.basename(tty))
        # Ascend from the tty's device link to the USB device dir (has idVendor).
        for _ in range(8):
            vid_path = os.path.join(node, "idVendor")
            if os.path.exists(vid_path):
                with open(vid_path) as f:
                    vendor = f.read().strip()
                if vendor == CH340_VENDOR:
                    return tty, os.path.basename(node)
                break  # a USB device, but not the CH340 — try the next tty
            parent = os.path.dirname(node)
            if parent == node:
                break
            node = parent
    raise SystemExit("no CH340 (%s) USB-serial device found (checked %s)"
                     % (CH340_VENDOR, ", ".join(candidates) or "no ttyUSB*"))


def identify_uptime(dev, tag):
    """Identify the MCU and confirm liveness by reading uptime twice within the
    same session (this board auto-resets on port-open, so cross-session uptime
    is not continuous; within-session advance proves the MCU is running)."""
    p = serial.Serial(baudrate=250000, timeout=0.05, exclusive=True, port=None)
    p.dtr = False
    p.rts = False
    p.port = dev
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


def set_authorized(usb_node, val):
    subprocess.run(
        ["sudo", "sh", "-c",
         f"echo {val} > /sys/bus/usb/devices/{usb_node}/authorized"],
        check=True)


def wait_for_dev(dev, present, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if os.path.exists(dev) == present:
            return True
        time.sleep(0.2)
    return False


def main():
    dev_arg = sys.argv[1] if len(sys.argv) > 1 else None
    dev, usb_node = resolve_ch340(dev_arg)
    print(f"=== TEST: USB re-enumeration / reboot recovery "
          f"({dev}, usb node {usb_node}) ===")
    ok_before = identify_uptime(dev, "before")

    deauthorized = False
    try:
        print("  deauthorizing USB device (forced disconnect) ...")
        set_authorized(usb_node, 0)
        deauthorized = True
        disappeared = wait_for_dev(dev, present=False)
        if disappeared:
            print(f"  {dev} removed (host sees disconnect)")
        else:
            # No disconnect actually happened — the test proved nothing.
            print(f"  FAIL: {dev} never disappeared — no real disconnect to recover from")
        time.sleep(2.0)

        print("  reauthorizing USB device (reconnect) ...")
        set_authorized(usb_node, 1)
        deauthorized = False
        if not wait_for_dev(dev, present=True):
            print(f"  RESULT: FAIL — {dev} did not return after reconnect")
            return 1
        print(f"  {dev} re-enumerated")
        time.sleep(1.5)  # settle for udev to set permissions

        ok_after = identify_uptime(dev, "after")

        print("  (this board auto-resets the MCU on port-open, so the 'after' "
              "session is a fresh boot — this proves re-enumeration + reboot "
              "recovery, not survival across the disconnect)")
        result = disappeared and ok_before and ok_after
        print("  RESULT:",
              "PASS — device disconnected, re-enumerated, and MCU re-identified"
              if result else "FAIL")
        return 0 if result else 1
    finally:
        # Never leave the device deauthorized, even if the test aborts.
        if deauthorized:
            try:
                set_authorized(usb_node, 1)
                print("  (cleanup) re-authorized USB device")
            except Exception as e:
                print(f"  WARN: failed to re-authorize {usb_node}: {e}")


if __name__ == "__main__":
    sys.exit(main())
