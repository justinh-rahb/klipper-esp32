#!/bin/sh
set -eu

build_dir="$(mktemp -d "${TMPDIR:-/tmp}/pandabreath-timer-test.XXXXXX")"
trap 'rm -rf "$build_dir"' EXIT HUP INT TERM

"${CC:-cc}" -std=c11 -Wall -Wextra -Werror \
    -Icomponents/klipper/board \
    tests/test_timer_math.c -o "$build_dir/test_timer_math"
"$build_dir/test_timer_math"
