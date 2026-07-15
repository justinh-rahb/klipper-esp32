#!/bin/sh
# Copyright (C) 2026 Justin Hayes <justinh@rahb.ca>
# Distributed under the terms of the GNU GPLv3 license.

set -eu

binary="${TMPDIR:-/tmp}/pandabreath-test-pwm-math"
cc -std=c11 -Wall -Wextra -Werror tests/test_pwm_math.c -o "$binary"
"$binary"
