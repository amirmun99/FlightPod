#!/usr/bin/env bash
# Reverse install.sh.
#
# Stops + disables the systemd unit and removes /opt/flightpaper. By
# default leaves /etc/flightpaper/secure (device identity + paired
# clients) alone — pass --purge to also wipe secrets and the config.

set -Eeuo pipefail

INSTALL_PREFIX="/opt/flightpaper"
CONFIG_DIR="/etc/flightpaper"
SECURE_DIR="$CONFIG_DIR/secure"
SERVICE_NAME="flightpaper"
SERVICE_UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
LOG_DIR="/var/log/flightpaper"

PURGE=0

log()  { printf '\033[1;36m[uninstall]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[uninstall]\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m[uninstall]\033[0m %s\n' "$*" >&2; exit 1; }

for arg in "$@"; do
  case "$arg" in
    --purge) PURGE=1 ;;
    -h|--help)
      cat <<EOF
Usage: $0 [--purge]

  (default)  Stop + remove the service and /opt/flightpaper.
             ${CONFIG_DIR} and ${SECURE_DIR} are preserved so re-installing
             keeps the device identity + paired phones.
  --purge    Also delete ${CONFIG_DIR} (config + secure dir + logs).
EOF
      exit 0
      ;;
    *) fail "Unknown argument: $arg" ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  fail "Run as root: sudo $0"
fi

# Confirm interactively unless overridden.
if [[ "${FLIGHTPAPER_FORCE:-0}" != "1" ]]; then
  msg="This will stop ${SERVICE_NAME} and remove ${INSTALL_PREFIX}."
  if [[ $PURGE -eq 1 ]]; then
    msg+=" It will ALSO delete ${CONFIG_DIR} (config + secrets)."
  fi
  echo "$msg"
  read -r -p "Continue? [y/N] " ans
  [[ "${ans:-N}" =~ ^[Yy]$ ]] || fail "Aborted."
fi

if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
  log "Stopping + disabling ${SERVICE_NAME}…"
  systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
  systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
fi

if [[ -f "${SERVICE_UNIT}" ]]; then
  log "Removing systemd unit…"
  rm -f "${SERVICE_UNIT}"
  systemctl daemon-reload
fi

if [[ -d "${INSTALL_PREFIX}" ]]; then
  log "Removing ${INSTALL_PREFIX}…"
  rm -rf "${INSTALL_PREFIX}"
fi

if [[ $PURGE -eq 1 ]]; then
  if [[ -d "${CONFIG_DIR}" ]]; then
    log "Purging ${CONFIG_DIR}…"
    rm -rf "${CONFIG_DIR}"
  fi
  if [[ -d "${LOG_DIR}" ]]; then
    log "Purging ${LOG_DIR}…"
    rm -rf "${LOG_DIR}"
  fi
else
  log "Leaving ${CONFIG_DIR} (re-install will reuse the device identity)."
  log "Pass --purge to also wipe it."
fi

log "Done."
