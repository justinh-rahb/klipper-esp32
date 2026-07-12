#!/bin/sh
set -eu

profile="${1:-dev}"
case "$profile" in
    dev|panda) ;;
    *)
        echo "usage: $0 [dev|panda]" >&2
        exit 2
        ;;
esac

if ! command -v idf.py >/dev/null 2>&1; then
    echo "idf.py is not on PATH; source the ESP-IDF export script first" >&2
    exit 1
fi

build_dir="build-${profile}"
sdkconfig="sdkconfig.${profile}"
defaults="sdkconfig.defaults;sdkconfig.${profile}.defaults"

# Pass one compiles the MCU objects and generates Klipper's dictionary source.
SDKCONFIG_DEFAULTS="$defaults" idf.py -B "$build_dir" \
    -DSDKCONFIG="$sdkconfig" build

# Pass two compiles that generated source into the final firmware image.
SDKCONFIG_DEFAULTS="$defaults" idf.py -B "$build_dir" \
    -DSDKCONFIG="$sdkconfig" build

python3 ./validate_build.py --profile "$profile" \
    "$build_dir/esp-idf/klipper/klipper.dict"

echo "firmware: $build_dir/panda_breath.bin"
echo "dictionary: $build_dir/esp-idf/klipper/klipper.dict"
