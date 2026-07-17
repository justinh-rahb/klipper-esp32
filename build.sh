#!/bin/sh
# Copyright (C) 2026 Justin Hayes <justinh@rahb.ca>
# Distributed under the terms of the GNU GPLv3 license.

set -eu

profile="${1:-dev}"
target="${2:-esp32c3}"
case "$profile" in
    dev|panda|bentobox) ;;
    *)
        echo "usage: $0 [dev|panda|bentobox] [esp32c3|esp32s3]" >&2
        exit 2
        ;;
esac

case "$target" in
    esp32c3|esp32s3) ;;
    *)
        echo "usage: $0 [dev|panda|bentobox] [esp32c3|esp32s3]" >&2
        exit 2
        ;;
esac

if [ "$target" != esp32c3 ] && [ "$profile" != dev ]; then
    echo "$profile is an ESP32-C3 product profile; use the dev profile for $target" >&2
    exit 2
fi

if ! command -v idf.py >/dev/null 2>&1; then
    echo "idf.py is not on PATH; source the ESP-IDF export script first" >&2
    exit 1
fi

build_dir="build-${target}-${profile}"
sdkconfig="sdkconfig.${target}.${profile}"
defaults="sdkconfig.defaults;targets/${target}.defaults;profiles/${profile}.defaults"
project_name="klipper_${target}"

# Pass one compiles the MCU objects and generates Klipper's dictionary source.
IDF_TARGET="$target" SDKCONFIG_DEFAULTS="$defaults" idf.py -B "$build_dir" \
    -DSDKCONFIG="$sdkconfig" build

# Pass two compiles that generated source into the final firmware image.
IDF_TARGET="$target" SDKCONFIG_DEFAULTS="$defaults" idf.py -B "$build_dir" \
    -DSDKCONFIG="$sdkconfig" build

python3 ./validate_build.py --profile "$profile" --target "$target" \
    "$build_dir/esp-idf/klipper/klipper.dict"

echo "firmware: $build_dir/${project_name}.bin"
echo "dictionary: $build_dir/esp-idf/klipper/klipper.dict"
