#!/usr/bin/env bash
# FlightPaper Pi installer.
#
# Run from the repo root or from this directory:
#   sudo apps/pi/install.sh
#
# What it does:
#   1. Sanity-checks the host (Raspberry Pi OS Bookworm or compatible,
#      apt available, run as root).
#   2. Installs system packages: python3.11+, venv, build essentials,
#      libsodium (for PyNaCl wheels that need it), fonts-dejavu-core,
#      libopenjp2-7 (Pillow JPEG2000), git.
#   3. Enables SPI + I2C via raspi-config (the Waveshare HAT + PiSugar 3
#      both need these).
#   4. Copies the package to /opt/flightpaper, creates a venv at
#      /opt/flightpaper/.venv, installs the `flightpaper` package with the
#      hardware extras, and vendors the Waveshare `waveshare_epd` panel
#      library (not published to PyPI) into the venv.
#   5. Creates /etc/flightpaper/ (config) + /etc/flightpaper/secure/
#      (pairing state, device identity) with 0700 root:root.
#   6. Installs the systemd unit, enables it, and starts it.
#   7. Prints follow-up commands.
#
# Idempotent: re-running re-copies the package + restarts the service,
# but does not destroy /etc/flightpaper/secure (the device identity +
# paired clients).

set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INSTALL_PREFIX="/opt/flightpaper"
CONFIG_DIR="/etc/flightpaper"
SECURE_DIR="$CONFIG_DIR/secure"
SERVICE_NAME="flightpaper"
SERVICE_UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/var/log/flightpaper"

# Waveshare e-Paper library — not on PyPI. The 2.13" driver shim does
# `from waveshare_epd import epd2in13_V2`, so we vendor this package from
# Waveshare's repo into the venv. Override the ref/source via env if needed.
WAVESHARE_REPO="${WAVESHARE_EPD_REPO:-https://github.com/waveshare/e-Paper.git}"
WAVESHARE_LIB_SUBDIR="RaspberryPi_JetsonNano/python/lib/waveshare_epd"

APT_PACKAGES=(
  python3
  python3-venv
  python3-dev
  python3-pip
  build-essential
  libsodium-dev
  libopenjp2-7
  libtiff6
  fonts-dejavu-core
  i2c-tools
  git
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log()  { printf '\033[1;36m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[install]\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m[install]\033[0m %s\n' "$*" >&2; exit 1; }

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "This script must run as root. Try: sudo $0"
  fi
}

require_apt() {
  if ! command -v apt-get >/dev/null 2>&1; then
    fail "apt-get is required; this script expects a Debian-based Pi OS."
  fi
}

confirm_pi() {
  if ! grep -q 'Raspberry Pi' /proc/cpuinfo 2>/dev/null && \
     ! grep -q 'BCM' /proc/cpuinfo 2>/dev/null; then
    warn "/proc/cpuinfo does not look like a Raspberry Pi."
    warn "Continuing anyway — set FLIGHTPAPER_FORCE=1 to silence this."
    if [[ "${FLIGHTPAPER_FORCE:-0}" != "1" ]]; then
      read -r -p "Continue? [y/N] " ans
      [[ "${ans:-N}" =~ ^[Yy]$ ]] || fail "Aborted."
    fi
  fi
}

# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

install_packages() {
  log "Updating apt cache…"
  apt-get update -qq
  log "Installing system packages: ${APT_PACKAGES[*]}"
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${APT_PACKAGES[@]}"
}

enable_interfaces() {
  if command -v raspi-config >/dev/null 2>&1; then
    log "Enabling SPI + I2C via raspi-config…"
    raspi-config nonint do_spi 0 || warn "raspi-config do_spi failed (continuing)."
    raspi-config nonint do_i2c 0 || warn "raspi-config do_i2c failed (continuing)."
  else
    warn "raspi-config not present; enable SPI + I2C manually before first boot."
  fi
}

stage_package() {
  log "Copying package to ${INSTALL_PREFIX}…"
  mkdir -p "${INSTALL_PREFIX}"
  # Pin the source tree to the directory containing this script.
  rsync -a --delete \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.egg-info/' \
    --exclude='.pytest_cache/' \
    "${SCRIPT_DIR}/" "${INSTALL_PREFIX}/"
}

build_venv() {
  log "Creating venv at ${INSTALL_PREFIX}/.venv…"
  if [[ ! -d "${INSTALL_PREFIX}/.venv" ]]; then
    python3 -m venv "${INSTALL_PREFIX}/.venv"
  fi
  log "Upgrading pip + installing flightpaper[hardware]…"
  "${INSTALL_PREFIX}/.venv/bin/pip" install --upgrade pip wheel setuptools >/dev/null
  "${INSTALL_PREFIX}/.venv/bin/pip" install -e "${INSTALL_PREFIX}[hardware]"
}

install_waveshare_epd() {
  # `waveshare_epd` is not on PyPI; without it the display driver silently
  # falls back to the null driver and nothing renders to the panel. Vendor
  # it from Waveshare's repo into the venv's site-packages. Failures here
  # are non-fatal — the service still runs, just with no physical display.
  local py="${INSTALL_PREFIX}/.venv/bin/python"
  if "${py}" -c "import waveshare_epd" >/dev/null 2>&1; then
    log "waveshare_epd already present in venv — skipping."
    return
  fi

  log "Vendoring waveshare_epd from ${WAVESHARE_REPO}…"
  local site tmp
  site="$("${py}" -c "import site; print(site.getsitepackages()[0])")"
  tmp="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap "rm -rf '${tmp}'" RETURN

  # Blobless + sparse so we pull only the python lib, not the whole repo
  # (it bundles images/docs for every panel — heavy on a Pi's SD card).
  if ! git clone --depth 1 --filter=blob:none --sparse \
        "${WAVESHARE_REPO}" "${tmp}/e-Paper" >/dev/null 2>&1 \
     || ! git -C "${tmp}/e-Paper" sparse-checkout set "${WAVESHARE_LIB_SUBDIR}" >/dev/null 2>&1; then
    warn "Could not fetch the Waveshare library (network?). The panel will use"
    warn "the null driver until you vendor waveshare_epd manually."
    return
  fi

  local src="${tmp}/e-Paper/${WAVESHARE_LIB_SUBDIR}"
  if [[ ! -d "${src}" ]]; then
    warn "Waveshare repo layout changed; ${WAVESHARE_LIB_SUBDIR} not found."
    warn "Skipping — the panel will use the null driver."
    return
  fi

  rm -rf "${site}/waveshare_epd"
  cp -r "${src}" "${site}/"
  if "${py}" -c "from waveshare_epd import epd2in13_V2" >/dev/null 2>&1; then
    log "waveshare_epd vendored into ${site}."
  else
    warn "waveshare_epd copied but import still fails — check the venv + SPI."
  fi
}

create_config_dirs() {
  log "Creating ${CONFIG_DIR} + ${SECURE_DIR} (0700 root:root)…"
  install -d -m 0755 -o root -g root "${CONFIG_DIR}"
  install -d -m 0700 -o root -g root "${SECURE_DIR}"
  install -d -m 0755 -o root -g root "${LOG_DIR}"

  if [[ ! -f "${CONFIG_DIR}/config.yml" ]]; then
    log "Seeding ${CONFIG_DIR}/config.yml from config.example.yml"
    install -m 0644 -o root -g root \
      "${INSTALL_PREFIX}/config.example.yml" \
      "${CONFIG_DIR}/config.yml"
  else
    log "${CONFIG_DIR}/config.yml already present — leaving alone."
  fi
}

install_systemd() {
  log "Installing systemd unit → ${SERVICE_UNIT}"
  install -m 0644 -o root -g root \
    "${INSTALL_PREFIX}/systemd/flightpaper.service" \
    "${SERVICE_UNIT}"
  log "Reloading systemd, enabling + starting ${SERVICE_NAME}…"
  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}"
  systemctl restart "${SERVICE_NAME}"
}

print_followups() {
  cat <<EOF

\033[1;32m[install]\033[0m FlightPaper installed.

Useful commands:
  sudo systemctl status ${SERVICE_NAME}
  sudo systemctl restart ${SERVICE_NAME}
  sudo journalctl -u ${SERVICE_NAME} -f
  sudo nano ${CONFIG_DIR}/config.yml   # then: sudo systemctl restart ${SERVICE_NAME}

PiSugar 3 (optional but recommended):
  curl https://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash
  systemctl status pisugar-server      # FlightPaper auto-detects on 127.0.0.1:8423

To reset pairing (forces a new QR on next boot):
  sudo /opt/flightpaper/.venv/bin/python /opt/flightpaper/scripts/reset_pairing.py
  sudo systemctl restart ${SERVICE_NAME}

To uninstall:
  sudo ${SCRIPT_DIR}/uninstall.sh

EOF
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
  require_root
  require_apt
  confirm_pi

  install_packages
  enable_interfaces
  stage_package
  build_venv
  install_waveshare_epd
  create_config_dirs
  install_systemd
  print_followups
}

main "$@"
