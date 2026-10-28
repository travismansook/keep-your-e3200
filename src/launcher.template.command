#!/bin/bash
# One launcher for the validated Wi-Fi E3200 responder and general DHCP forwarder.
# Both components retain their existing network behavior and share stop controls.
umask 077
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd -P) || exit 1
STATE_DIR=${E3200_STATE_DIR:?Start the guided helper}
IFACE=${E3200_ETHERNET:?Start the guided helper}
SERVER_IP=${E3200_SERVER:?Start the guided helper}
HELPER_MAC=${E3200_ETHERNET_MAC:?Start the guided helper}
TRIAL_SECONDS=600
RUN_SECONDS=600
MODE=combined-normal
DRY_RUN=0
LOCK_HELD=0
MANAGED_RUNTIME=""
MANAGED_RUNNER=""
MANAGED_LOGGER=""
MANAGED_STOPPED=1

finish() {
  EXIT_STATUS=$?
  trap '' INT TERM HUP
  if [ -n "$MANAGED_RUNTIME" ]; then
    printf '\nStopping the managed helper...\n'
    : > "$MANAGED_RUNTIME/stop.request"
    if [ -z "$MANAGED_RUNNER" ]; then
      # Cancellation during setup: no privileged runner has been registered.
      # A runner launched at the signal boundary also sees stop.request before
      # spawning its worker. A waiting logger has no work to retain.
      [ -z "$MANAGED_LOGGER" ] || kill -TERM "$MANAGED_LOGGER" 2>/dev/null || true
      MANAGED_STOPPED=1
    fi
    # The privileged supervisor already holds the rights needed to stop its child;
    # cancellation never depends on a fresh sudo password or a foreground pipeline.
    for ((stop_tick=0; stop_tick<80; stop_tick++)); do
      [ "$MANAGED_STOPPED" != 1 ] || break
      if [ -f "$MANAGED_RUNTIME/stopped" ]; then
        MANAGED_STOPPED=1
        break
      fi
      /bin/sleep 0.1
    done
    if [ "$MANAGED_STOPPED" = 1 ]; then
      [ -z "$MANAGED_RUNNER" ] || wait "$MANAGED_RUNNER" 2>/dev/null || true
      [ -z "$MANAGED_LOGGER" ] || kill -TERM "$MANAGED_LOGGER" 2>/dev/null || true
      [ -z "$MANAGED_LOGGER" ] || wait "$MANAGED_LOGGER" 2>/dev/null || true
      printf 'Helper stopped.\n'
    else
      printf 'Stop is not yet confirmed. Run this program with --stop to request shutdown.\n' >&2
    fi
  fi
  if [ "$LOCK_HELD" = 1 ] && [ "$MANAGED_STOPPED" = 1 ]; then
    rmdir "$STATE_DIR/running.lock" 2>/dev/null || true
  fi
  return "$EXIT_STATUS"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

die() {
  printf '\nStopped: %s\n' "$*" >&2
  if [ -t 0 ] && [ "$DRY_RUN" = 0 ]; then
    read -r -p 'Press Return to close. ' _
  fi
  exit 1
}

run_managed() {
  MANAGED_LOG=$1
  shift
  /usr/bin/sudo -v || die 'Administrator access is needed to run this helper.'
  MANAGED_RUNTIME=$(mktemp -d "$STATE_DIR/run-$RUN_ID.XXXXXX") || die 'Could not create a private runtime folder.'
  MANAGED_STOPPED=0
  printf '%s\n' "$$" > "$MANAGED_RUNTIME/launcher.pid"
  : > "$MANAGED_LOG" || die 'Could not create the log file.'
  cat > "$MANAGED_RUNTIME/supervisor.sh" <<'SUPERVISOR'
#!/bin/bash
umask 077
runtime=$1
launcher_pid=$2
logger_pid=$3
max_seconds=$4
shift 4
worker_pid=""
wake_pid=""

cleanup_worker() {
  worker_status=$?
  trap - EXIT INT TERM HUP
  if [ -n "$worker_pid" ]; then
    if kill -0 "$worker_pid" 2>/dev/null; then
      kill -TERM "$worker_pid" 2>/dev/null || true
      for ((term_tick=0; term_tick<40; term_tick++)); do
        kill -0 "$worker_pid" 2>/dev/null || break
        /bin/sleep 0.1
      done
      if kill -0 "$worker_pid" 2>/dev/null; then
        kill -KILL "$worker_pid" 2>/dev/null || true
      fi
    fi
    wait "$worker_pid" 2>/dev/null || true
  fi
  if [ -n "$wake_pid" ]; then
    kill -TERM "$wake_pid" 2>/dev/null || true
    wait "$wake_pid" 2>/dev/null || true
  fi
  # The display follower is also ours. Stop it even if the launcher was killed.
  kill -TERM "$logger_pid" 2>/dev/null || true
  printf '%s\n' "$worker_status" > "$runtime/stopped"
  return "$worker_status"
}
trap cleanup_worker EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
trap 'exit 141' PIPE
if [ -e "$runtime/stop.request" ] || ! kill -0 "$launcher_pid" 2>/dev/null; then
  exit 0
fi

"$@" &
worker_pid=$!
printf '%s\n' "$worker_pid" > "$runtime/worker.pid"
# caffeinate uses process-exit notification, so even an unreaped launcher zombie
# releases this watcher. kill -0 on the launcher alone cannot detect that case.
/usr/bin/caffeinate -i -w "$launcher_pid" &
wake_pid=$!
started_seconds=$SECONDS
while kill -0 "$worker_pid" 2>/dev/null; do
  if [ "$max_seconds" -gt 0 ] && [ "$((SECONDS - started_seconds))" -ge "$max_seconds" ]; then
    printf "TRIAL_FINISHED: automatic stop after %s seconds.\n" "$max_seconds"
    : > "$runtime/timed-out"
    exit 0
  fi
  if [ -e "$runtime/stop.request" ] || ! kill -0 "$wake_pid" 2>/dev/null; then
    exit 0
  fi
  /bin/sleep 0.2
done
wait "$worker_pid"
worker_status=$?
if [ -e "$runtime/stop.request" ]; then worker_status=0; fi
worker_pid=""
exit "$worker_status"
SUPERVISOR
  chmod 700 "$MANAGED_RUNTIME/supervisor.sh" || die 'Could not protect the supervisor.'
  # Write the worker directly to a regular log file. A terminal hangup must not
  # break a logging pipe and bypass graceful DHCP lease-file shutdown.
  /usr/bin/tail -n +1 -f "$MANAGED_LOG" &
  MANAGED_LOGGER=$!
  /usr/bin/sudo -n /bin/bash "$MANAGED_RUNTIME/supervisor.sh" "$MANAGED_RUNTIME" "${E3200_PORTABLE_PARENT_PID:-$$}" "$MANAGED_LOGGER" "$RUN_SECONDS" "$@" >> "$MANAGED_LOG" 2>&1 &
  MANAGED_RUNNER=$!
  # wait is interruptible. Ctrl+C runs the EXIT cleanup immediately, which asks
  # the privileged supervisor to terminate and reap the actual worker.
  wait "$MANAGED_RUNNER"
  MANAGED_STATUS=$?
  if [ -f "$MANAGED_RUNTIME/stopped" ]; then
    MANAGED_STOPPED=1
  else
    # A failed sudo invocation started no supervisor/worker; let the Stop command
    # handle uncertainty rather than claiming successful cleanup.
    : > "$MANAGED_RUNTIME/stop.request"
  fi
  if [ "$MANAGED_STOPPED" = 1 ]; then
    kill -TERM "$MANAGED_LOGGER" 2>/dev/null || true
    wait "$MANAGED_LOGGER" 2>/dev/null || true
    MANAGED_RUNTIME=""
    MANAGED_RUNNER=""
    MANAGED_LOGGER=""
  fi
  return "$MANAGED_STATUS"
}


E3200_MAC=${E3200_MAC:?Start the guided helper}
E3200_IP=${E3200_IP:?Start the guided helper}
WIFI_IFACE=${E3200_WIFI:?Start the guided helper}
WIFI_IP=${E3200_WIFI_IP:?Start the guided helper}
SUBNET_MASK=${E3200_SUBNET_MASK:?Start the guided helper}
SUBNET_HEX=${E3200_SUBNET_HEX:?Start the guided helper}
SUBNET_NETWORK=${E3200_NETWORK:?Start the guided helper}
DNS_IP=${E3200_DNS:?Start the guided helper}
LEASE_MINUTES=${E3200_LEASE_MINUTES:?Start the guided helper}

OPT125="00:00:0d:e9:21:04:06:38:38:30:33:35:35:05:10:47:30:30:30:30:30:30:30:30:30:30:30:30:30:30:30:06:05:47:33:31:30:30"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --trial) MODE=combined-trial ;;
    --trial-seconds)
      [ "$#" -ge 2 ] || die '--trial-seconds needs a number.'
      TRIAL_SECONDS=$2; MODE=combined-trial; shift ;;
    --state-dir)
      [ "$#" -ge 2 ] || die '--state-dir needs an absolute folder path.'
      STATE_DIR=$2; shift ;;
    *) die "Unknown option: $1" ;;
  esac
  shift
done
case "$STATE_DIR" in /*) ;; *) die 'Use an absolute data folder path.' ;; esac
case "$STATE_DIR" in *$'\n'*|*$'\r'*) die 'The data folder cannot contain line breaks.' ;; esac
case "$TRIAL_SECONDS" in ''|*[!0-9]*) die 'Trial duration must be a number.' ;; esac
[ "${#TRIAL_SECONDS}" -le 4 ] || die 'Trial duration must be between 10 and 1800 seconds.'
TRIAL_SECONDS=$((10#$TRIAL_SECONDS))
[ "$TRIAL_SECONDS" -ge 10 ] && [ "$TRIAL_SECONDS" -le 1800 ] || die 'Trial duration must be between 10 and 1800 seconds.'
if [ "$MODE" = combined-normal ]; then RUN_SECONDS=0; else RUN_SECONDS=$TRIAL_SECONDS; fi
BRIDGE="$SCRIPT_DIR/forwarder.py"
WORKER="$SCRIPT_DIR/combined_worker.py"
for source_file in "$BRIDGE" "$WORKER"; do
  [ -f "$source_file" ] && [ ! -L "$source_file" ] && [ -O "$source_file" ] || die 'An included program file is missing. Download the helper again.'
done
PYTHON=${E3200_PYTHON:?Start the guided helper}
[ -x "$PYTHON" ] || die 'The bundled program could not be opened.'

"$PYTHON" "$BRIDGE" --check-only || die 'The forwarding component failed its offline checks.'
DNSMASQ="$SCRIPT_DIR/dnsmasq"
[ -x "$DNSMASQ" ] || die 'The included DHCP engine is missing. Download the helper again.'
EXPECTED_BINARY_SHA256=${E3200_ENGINE_SHA256:?Start the guided helper}
ACTUAL_BINARY_SHA256=$(/usr/bin/shasum -a 256 "$DNSMASQ" | /usr/bin/awk '{print $1}')
[ "$ACTUAL_BINARY_SHA256" = "$EXPECTED_BINARY_SHA256" ] || die 'The private DHCP executable differs from the tested build.'
if [ "$DRY_RUN" = 0 ]; then
  CONNECTION_INFO=$(/sbin/ifconfig "$IFACE" 2>/dev/null) || die 'Connect your selected Ethernet adapter directly to an Ethernet port on the E3200.'
  ACTUAL_MAC=$(printf '%s\n' "$CONNECTION_INFO" | awk '$1 == "ether" {print tolower($2); exit}')
  [ "$ACTUAL_MAC" = "$HELPER_MAC" ] || die 'The selected Ethernet adapter changed. Reconnect it or run setup again.'
  printf '%s\n' "$CONNECTION_INFO" | awk '$1 == "status:" && $2 == "active" {found=1} END {exit !found}' || die 'Ethernet link is inactive.'
  WIFI_INFO=$(/sbin/ifconfig "$WIFI_IFACE" 2>/dev/null) || die 'Wi-Fi must also be connected for the E3200 compatibility response.'
  printf '%s\n' "$WIFI_INFO" | awk '$1 == "status:" && $2 == "active" {found=1} END {exit !found}' || die 'Keep Wi-Fi connected for DHCP transport. Ethernet remains the Mac internet connection.'
  CURRENT_WIFI_IP=$(/usr/sbin/ipconfig getifaddr "$WIFI_IFACE" 2>/dev/null)
  [ "$CURRENT_WIFI_IP" = "$WIFI_IP" ] || die "The helper expects the existing Wi-Fi address $WIFI_IP; found ${CURRENT_WIFI_IP:-none}. No settings were changed."
  WIFI_MASK=$(printf '%s\n' "$WIFI_INFO" | awk -v ip="$WIFI_IP" '$1 == "inet" && $2 == ip {print $4; exit}')
  [ "$WIFI_MASK" = "$SUBNET_HEX" ] || [ "$WIFI_MASK" = "$SUBNET_MASK" ] || die 'The Wi-Fi network changed. Run setup again for your home network.'
  printf '\nChecking the Mac Wi-Fi control connection...\n'
  /usr/bin/curl --interface "$WIFI_IFACE" -4 --connect-timeout 3 --max-time 6 -f -sS -o /dev/null https://www.google.com/generate_204 || die 'The Wi-Fi control connection has no IPv4 internet. No helper was started.'
fi
if [ -e "$STATE_DIR" ] || [ -L "$STATE_DIR" ]; then
  [ ! -L "$STATE_DIR" ] && [ -d "$STATE_DIR" ] && [ -O "$STATE_DIR" ] || die 'Use a normal data folder owned by your account.'
else
  mkdir -p "$STATE_DIR" || die 'Could not create the data folder.'
fi
chmod 700 "$STATE_DIR" || die 'Could not protect the data folder.'
RUN_ID="$(date +%Y%m%d-%H%M%S)-$$"
CONF="$STATE_DIR/config-combined-$RUN_ID.conf"
LOG="$STATE_DIR/combined-$RUN_ID.log"
LEASES="$STATE_DIR/upstream-only.leases"
RUN_USER=$(/usr/bin/id -un)
RUN_GROUP=$(/usr/bin/id -gn)
cat > "$CONF" <<EOF
# E3200 only on the previously working Wi-Fi path.
# CHR30A remains responsible for normal Ethernet/Wi-Fi client DHCP.
port=0
interface=$WIFI_IFACE
except-interface=$IFACE
except-interface=lo0
bind-interfaces
user=$RUN_USER
group=$RUN_GROUP
dhcp-range=$SUBNET_NETWORK,static,$SUBNET_MASK,${LEASE_MINUTES}m
dhcp-host=$E3200_MAC,$E3200_IP,set:e3200
dhcp-ignore=tag:!known
dhcp-option=tag:e3200,tag:$WIFI_IFACE,option:router,$SERVER_IP
dhcp-option=tag:e3200,tag:$WIFI_IFACE,option:dns-server,$DNS_IP
dhcp-option-force=tag:e3200,tag:$WIFI_IFACE,60,"ARCADYAN"
dhcp-option-force=tag:e3200,tag:$WIFI_IFACE,125,$OPT125
dhcp-leasefile=$LEASES
log-dhcp
log-facility=-
EOF
[ "$?" = 0 ] || die 'Could not write the extender configuration.'
"$DNSMASQ" --test --conf-file="$CONF" || die 'The extender configuration did not validate.'
if [ "$DRY_RUN" = 1 ]; then
  printf '\nValidated only: no network checks or DHCP service were run.\n'
  printf 'E3200 compatibility stays on %s; general client forwarding uses the chosen Ethernet and Wi-Fi connections.\n' "$WIFI_IFACE"
  printf 'Original lease data is preserved. E3200 lease file: %s\n' "$LEASES"
  printf 'Run limit: %s seconds (0 means until stopped). Config: %s\n' "$RUN_SECONDS" "$CONF"
  exit 0
fi
FORWARD_LOCK="$STATE_DIR/forwarder.lock"
if [ -e "$FORWARD_LOCK" ] || [ -L "$FORWARD_LOCK" ]; then
  [ ! -L "$FORWARD_LOCK" ] && [ -f "$FORWARD_LOCK" ] && [ -O "$FORWARD_LOCK" ] || die 'The forwarding lock has an unexpected ownership or type.'
else
  (set -o noclobber; : > "$FORWARD_LOCK") || die 'Could not create the forwarding lock.'
fi
"$PYTHON" --check-lock "$FORWARD_LOCK"
[ "$?" = 0 ] || die 'Stop the other helper with Ctrl+C before starting this one.'
/usr/bin/sudo -v || die 'Administrator access is needed to run both components.'
PORT_USERS=$(/usr/bin/sudo -n /usr/sbin/lsof -nP -iUDP:67 2>&1)
PORT_STATUS=$?
case "$PORT_STATUS" in
  0) die 'Another DHCP helper is active. Stop the other helper with Ctrl+C before opening this one.' ;;
  1) [ -z "$PORT_USERS" ] || die "Could not safely check the DHCP port: $PORT_USERS" ;;
  *) die "Could not check the DHCP port: $PORT_USERS" ;;
esac
mkdir "$STATE_DIR/running.lock" 2>/dev/null || die 'Another helper may be active. Stop its window with Ctrl+C first.'
LOCK_HELD=1
if [ -e "$LEASES" ] || [ -L "$LEASES" ]; then
  [ ! -L "$LEASES" ] && [ -f "$LEASES" ] && [ -O "$LEASES" ] || die 'The private client lease file has an unexpected type or ownership.'
else
  # Copy complete existing rows without changing their expiry timestamps.
  # Original lease files are only read; normal protocol renewals use our own file.
  LEASE_SOURCES=()
  for source_file in "$STATE_DIR/split-helper.leases" "$STATE_DIR/helper.leases" /tmp/e3200-helper.leases; do
    if [ -f "$source_file" ] && [ ! -L "$source_file" ] && [ -O "$source_file" ]; then
      LEASE_SOURCES[${#LEASE_SOURCES[@]}]=$source_file
    fi
  done
  if [ "${#LEASE_SOURCES[@]}" -gt 0 ]; then
    awk -v e="$E3200_MAC" -v ei="$E3200_IP" '
      NF >= 5 && tolower($2)==e && $3==ei {
        m=tolower($2)
        if (!(m in row) || $1==0 || (expires[m]!=0 && $1>expires[m])) {row[m]=$0; expires[m]=$1}
      }
      END {if (e in row) print row[e]}
    ' "${LEASE_SOURCES[@]}" > "$LEASES" || die 'Could not copy the existing E3200 record.'
  else
    : > "$LEASES" || die 'Could not create the private E3200 lease file.'
  fi
fi
RUN_UID=$(/usr/bin/id -u)
RUN_GID=$(/usr/bin/id -g)
printf '\nE3200 + Ethernet DHCP helper\n'
printf 'One window manages both working components.\n'
printf 'Keep the Mac on Using DHCP, Ethernet first, and both Ethernet/Wi-Fi connected.\n'
printf 'The E3200 compatibility response stays on Wi-Fi; ordinary leases come from the CHR30A.\n'
printf 'Wait for READY: E3200 and Ethernet helpers are running.\n'
if [ "$RUN_SECONDS" = 0 ]; then
  printf 'Runs until stopped. Ctrl+C in this window stops both components.\n'
else
  printf 'Timed run: stops both components after %s seconds.\n' "$RUN_SECONDS"
fi
printf 'If either component fails, both are stopped and the error is logged.\n'
printf 'Log: %s\n\n' "$LOG"
run_managed "$LOG" "$PYTHON" "$WORKER" --dnsmasq "$DNSMASQ" --config "$CONF" --bridge "$BRIDGE" --lock-file "$FORWARD_LOCK" --uid "$RUN_UID" --gid "$RUN_GID" --ethernet "$IFACE" --wifi "$WIFI_IFACE" --server "$SERVER_IP" --extender-mac "$E3200_MAC"
STATUS=$?
printf '\nCombined helper ended. Log: %s\n' "$LOG"
exit "$STATUS"
