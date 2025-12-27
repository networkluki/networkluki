#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_NAME="$(basename "$0")"
readonly LOCKS=(
  "/var/lib/dpkg/lock-frontend"
  "/var/lib/dpkg/lock"
  "/var/lib/apt/lists/lock"
  "/var/cache/apt/archives/lock"
)

log() {
  printf "[%s] %s\n" "$(date +"%Y-%m-%d %H:%M:%S")" "$*"
}

warn() {
  printf "[%s] WARN: %s\n" "$(date +"%Y-%m-%d %H:%M:%S")" "$*" >&2
}

die() {
  printf "[%s] ERROR: %s\n" "$(date +"%Y-%m-%d %H:%M:%S")" "$*" >&2
  exit 1
}

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME [--full] [--reboot] [--clean] [--wait <seconds>]

Options:
  --full         Run full-upgrade (dist-upgrade) after upgrade.
  --reboot       Reboot if a reboot is required.
  --clean        Run autoremove and clean after upgrade.
  --wait <sec>   Max seconds to wait for apt locks (default: 120).
  -h, --help     Show this help.

Environment:
  NO_COLOR=1     Disable colored output.
  APT_FORCE_Y=1  Force non-interactive upgrades (default: enabled).
EOF
}

color() {
  local code="$1"
  shift
  if [[ "${NO_COLOR:-}" == "1" ]]; then
    printf "%s" "$*"
  else
    printf "\033[%sm%s\033[0m" "$code" "$*"
  fi
}

wait_for_apt_locks() {
  local timeout="$1"
  local start
  start="$(date +%s)"

  while true; do
    local locked=0
    for lock in "${LOCKS[@]}"; do
      if fuser "$lock" >/dev/null 2>&1; then
        locked=1
        break
      fi
    done

    if [[ "$locked" -eq 0 ]]; then
      return 0
    fi

    if (( "$(date +%s)" - start >= timeout )); then
      return 1
    fi

    log "$(color "33" "Waiting for apt locks...")"
    sleep 3
  done
}

ensure_sudo() {
  if [[ "${EUID}" -eq 0 ]]; then
    echo ""
    return 0
  fi

  if ! command -v sudo >/dev/null 2>&1; then
    die "sudo is required to run this script."
  fi

  echo "sudo"
}

APT_Y="-y"
FULL_UPGRADE=0
DO_REBOOT=0
DO_CLEAN=0
LOCK_WAIT=120

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full)
      FULL_UPGRADE=1
      shift
      ;;
    --reboot)
      DO_REBOOT=1
      shift
      ;;
    --clean)
      DO_CLEAN=1
      shift
      ;;
    --wait)
      LOCK_WAIT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

if [[ "${APT_FORCE_Y:-1}" != "1" ]]; then
  APT_Y=""
fi

SUDO_CMD="$(ensure_sudo)"

trap 'die "Upgrade failed on line $LINENO."' ERR

log "$(color "36" "Starting system upgrade")"
log "Lock wait timeout: ${LOCK_WAIT}s"

if ! wait_for_apt_locks "$LOCK_WAIT"; then
  die "Timed out waiting for apt locks."
fi

log "Updating package lists..."
$SUDO_CMD apt-get update

log "Upgrading packages..."
$SUDO_CMD DEBIAN_FRONTEND=noninteractive apt-get upgrade $APT_Y \
  -o Dpkg::Options::="--force-confdef" \
  -o Dpkg::Options::="--force-confold"

if [[ "$FULL_UPGRADE" -eq 1 ]]; then
  log "Running full-upgrade..."
  $SUDO_CMD DEBIAN_FRONTEND=noninteractive apt-get full-upgrade $APT_Y \
    -o Dpkg::Options::="--force-confdef" \
    -o Dpkg::Options::="--force-confold"
fi

if [[ "$DO_CLEAN" -eq 1 ]]; then
  log "Cleaning up unused packages..."
  $SUDO_CMD apt-get autoremove $APT_Y
  $SUDO_CMD apt-get clean
fi

if [[ -f /var/run/reboot-required ]]; then
  warn "Reboot required."
  if [[ "$DO_REBOOT" -eq 1 ]]; then
    log "Rebooting now..."
    $SUDO_CMD reboot
  fi
else
  log "$(color "32" "Upgrade complete - no reboot required.")"
fi
