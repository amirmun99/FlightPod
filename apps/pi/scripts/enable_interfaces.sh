#!/usr/bin/env bash
# Standalone toggle for SPI + I2C via raspi-config.
#
# install.sh runs this automatically, but it's broken out so you can
# run it on its own (e.g. if SPI was disabled by a routine apt upgrade)
# or call only one of the two.

set -Eeuo pipefail

log() { printf '\033[1;36m[interfaces]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[interfaces]\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m[interfaces]\033[0m %s\n' "$*" >&2; exit 1; }

if [[ "${EUID}" -ne 0 ]]; then
  fail "Must run as root: sudo $0 [--spi] [--i2c]"
fi

if ! command -v raspi-config >/dev/null 2>&1; then
  fail "raspi-config not found. Are you on Raspberry Pi OS?"
fi

ENABLE_SPI=1
ENABLE_I2C=1

# Allow ./enable_interfaces.sh --spi to enable just SPI.
case "${1:-}" in
  --spi) ENABLE_I2C=0 ;;
  --i2c) ENABLE_SPI=0 ;;
  --both|"") ;;
  -h|--help)
    cat <<EOF
Usage: $0 [--spi | --i2c | --both]

  --spi    Enable SPI only (Waveshare ePaper).
  --i2c    Enable I2C only (PiSugar 3 fallback path; pisugar-server uses
           the local TCP socket and doesn't need raw I2C, but enabling it
           is harmless).
  --both   (default) Enable both.
EOF
    exit 0
    ;;
  *) fail "Unknown option: $1" ;;
esac

if [[ $ENABLE_SPI -eq 1 ]]; then
  log "Enabling SPI…"
  raspi-config nonint do_spi 0
fi
if [[ $ENABLE_I2C -eq 1 ]]; then
  log "Enabling I2C…"
  raspi-config nonint do_i2c 0
fi

log "Done. You may need to reboot for the changes to take effect."
