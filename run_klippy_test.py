#!/usr/bin/env python3
# Real Klippy host connection test for the Panda Breath MCU.
#
# Launches Klippy (from ~/klippy-env) against a minimal heater-free config,
# waits for "Klipper state: Ready", then uses the API server to read the two
# thermistor temperatures and drive the safe LED on GPIO6 through the full
# host->MCU path. Never configures GPIO18, so the heater lockout is untouched.

import json
import os
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KLIPPY = os.path.join(HERE, "components/klipper/klipper/klippy/klippy.py")
VENV_PY = os.environ.get("KLIPPY_PYTHON", os.path.expanduser("~/klippy-env/bin/python"))
if len(sys.argv) < 2:
    sys.exit("usage: run_klippy_test.py <klipper-config.cfg>")
CFG = sys.argv[1]
_RUNDIR = tempfile.mkdtemp(prefix="klippy-run-")
LOG = os.path.join(_RUNDIR, "klippy.log")
UDS = os.path.join(_RUNDIR, "klippy_uds")


def api(sock, method, params=None, _id=[0]):
    _id[0] += 1
    msg = {"id": _id[0], "method": method}
    if params is not None:
        msg["params"] = params
    sock.sendall(json.dumps(msg).encode() + b"\x03")
    buf = b""
    deadline = time.monotonic() + 5.0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"no API reply for {method}")
        # Bound the blocking recv so a silent MCU/host can't hang it forever.
        sock.settimeout(remaining)
        try:
            data = sock.recv(4096)
        except socket.timeout:
            raise TimeoutError(f"no API reply for {method}")
        if not data:
            raise ConnectionError(f"API socket closed awaiting {method}")
        buf += data
        while b"\x03" in buf:
            chunk, buf = buf.split(b"\x03", 1)
            resp = json.loads(chunk)
            if resp.get("id") == msg["id"]:
                return resp


def wait_ready(timeout=45):
    deadline = time.monotonic() + timeout
    seen = ""
    while time.monotonic() < deadline:
        try:
            with open(LOG) as f:
                seen = f.read()
        except FileNotFoundError:
            seen = ""
        if "Klipper state: Ready" in seen:
            return True, seen
        for marker in ("Config error", "Unable to open", "MCU error",
                       "Error configuring", "is not a valid", "Traceback"):
            if marker in seen:
                return False, seen
        time.sleep(0.5)
    return False, seen


def main():
    for p in (LOG, UDS):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
    print("=== TEST: real Klippy host connection ===")
    proc = subprocess.Popen(
        [VENV_PY, KLIPPY, CFG, "-l", LOG, "-a", UDS],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        ready, logtext = wait_ready()
        if not ready:
            print("  RESULT: FAIL — Klipper did not reach Ready")
            tail = "\n".join(logtext.splitlines()[-25:])
            print("  --- klippy.log tail ---\n" + tail)
            return 1
        # Pull the MCU/version line and clock-sync confirmation from the log
        for line in logtext.splitlines():
            if "Loaded MCU" in line or "mcu 'mcu'" in line or "Starting Klippy" in line:
                print("  " + line.strip())
        print("  Klipper state: Ready  (host connected, dictionary loaded, clock synced)")

        # Query temperatures + LED via API
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect(UDS)
        info = api(s, "info")
        print(f"  API info: klipper on {info['result'].get('cpu_info','?')[:40]}")
        q = api(s, "objects/query", {"objects": {
            "temperature_sensor chamber_ntc": ["temperature"],
            "temperature_sensor ptc_ntc": ["temperature"]}})
        st = q["result"]["status"]
        tc = st.get("temperature_sensor chamber_ntc", {}).get("temperature")
        tp = st.get("temperature_sensor ptc_ntc", {}).get("temperature")
        print(f"  host-read temps: chamber_ntc={tc}C  ptc_ntc={tp}C")

        # Drive the safe LED through the host
        api(s, "gcode/script", {"script": "SET_PIN PIN=led_k1 VALUE=1"})
        time.sleep(0.5)
        api(s, "gcode/script", {"script": "SET_PIN PIN=led_k1 VALUE=0"})
        print("  drove led_k1 (GPIO6) HIGH->LOW via host SET_PIN")
        s.close()

        ok = (tc is not None and tp is not None)
        print("  RESULT:", "PASS — full Klippy host stack connected and operated the MCU"
              if ok else "PARTIAL (connected but temps missing)")
        return 0 if ok else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
