# Authors and provenance

This repository combines original ESP32-family work with code derived from
earlier Klipper and `klipper_esp32` projects. The file-level notices and Git
history are the authoritative record; this document makes the major
contributions easier to find.

## Justin Hayes

Justin Hayes <justinh@rahb.ca> is the primary author and maintainer of the
ESP32-C3 and ESP32-S3 work in this repository, including:

- the ESP32-C3 board-profile architecture and standalone build layout;
- the Panda Breath hardware mapping and safety boundary;
- native USB Serial/JTAG transport integration and RMT NeoPixel support;
- 32-bit Klipper clock rollover handling on the ESP32-C3 GPTimer;
- the MCU probe and build-dictionary validation tools;
- the BentoBox profile, hardware-I2C integration, and LEDC hardware-PWM work;
- the ESP32-S3 target port, build separation, and development-board bring-up;
- the example configurations, profile defaults, host tests, and documentation.

## Upstream work

- Nikhil Robinson <nikhil@techprogeny.com> authored the original ESP32 Klipper
  port that provided the starting board layer and ESP-IDF integration.
- Kevin O'Connor and the Klipper contributors authored Klipper and its MCU
  protocol implementation, included here as a Git submodule.

See the repository history and individual source-file notices for more detailed
attribution.
