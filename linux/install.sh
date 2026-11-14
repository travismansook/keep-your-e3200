#!/bin/sh
# The same wrapper installs or updates the .deb. No compilation or OS reinstall.
set -eu
[ "$(uname -s)" = Linux ] || { echo 'Run this on the Pi/Linux computer, not the Mac.' >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo 'Run: sudo ./linux/install.sh' >&2; exit 1; }
case "${1-}" in ''|--update) ;; *) echo 'Usage: sudo ./linux/install.sh [--update]' >&2; exit 1 ;; esac
BASE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
command -v nmcli >/dev/null || { echo 'Use Raspberry Pi OS Lite with NetworkManager. This installer will not replace your network manager.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'systemd is required.' >&2; exit 1; }
command -v apt-get >/dev/null || { echo 'This package targets Raspberry Pi OS / Debian.' >&2; exit 1; }
for folder in /opt/keep-your-e3200 /etc/keep-your-e3200 /var/lib/keep-your-e3200 /var/cache/keep-your-e3200; do
    [ ! -L "$folder" ] || { echo "Refusing symbolic link: $folder" >&2; exit 1; }
done
(cd "$BASE" && sha256sum --check linux/SHA256SUMS)
# Select the package named by this release's verified manifest. Older .deb
# files may remain when a user extracts an update into the same folder.
PACKAGE_NAMES=$(awk 'NF == 2 && $2 ~ /^keep-your-e3200_[0-9A-Za-z.+~:-]+_all[.]deb$/ { print $2 }' "$BASE/linux/SHA256SUMS")
set -- $PACKAGE_NAMES
[ "$#" -eq 1 ] && [ -f "$BASE/$1" ] || { echo 'Keep this installer with its release manifest and matching .deb package.' >&2; exit 1; }
PACKAGE="$BASE/$1"
install -d -m 700 /var/cache/keep-your-e3200
# Debian keeps configuration separate from the program. The package scripts
# restart only a previously running service, retaining its boot preference.
apt-get update
apt-get install -y "$PACKAGE"
if [ -f /var/cache/keep-your-e3200/current.deb ] && ! cmp -s "$PACKAGE" /var/cache/keep-your-e3200/current.deb; then
    cp /var/cache/keep-your-e3200/current.deb /var/cache/keep-your-e3200/previous.deb
fi
install -m 600 "$PACKAGE" /var/cache/keep-your-e3200/current.deb
printf '\nInstalled/updated. Settings and existing lease data were kept.\n'
printf 'Run keep-your-e3200 for the menu, or keep-your-e3200 status.\n'
