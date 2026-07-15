#!/bin/sh
set -eu

binary="${TMPDIR:-/tmp}/pandabreath-test-pwm-math"
cc -std=c11 -Wall -Wextra -Werror tests/test_pwm_math.c -o "$binary"
"$binary"
