#!/usr/bin/env bash
#
# epcview uninstall.sh — remove every trace of epcview from the system.
#
# Usage:  sudo epcview-uninstall
#     or  sudo /opt/epcview-*/deploy/uninstall.sh
#
# Removes:
#   - /opt/epcview-*                           every installed version
#   - /usr/local/bin/epcview                   the launcher
#   - /usr/local/sbin/epcview-uninstall        this script (last)
#   - /etc/epcview                             system config + example
#   - $SUDO_USER's ~/.config/epcview/          per-user config (if invoked
#                                              via sudo by a normal user)
#   - $SUDO_USER's ~/.config/systemd/user/epcview.service  if present

set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
    echo "✗ This uninstaller needs root."
    echo "  Re-run with:  sudo $0"
    exit 1
fi

removed_anything=0

remove_path() {
    local path="$1"
    if [[ -e "$path" || -L "$path" ]]; then
        rm -rf "$path"
        echo "  - removed $path"
        removed_anything=1
    fi
}

# 1. Versioned install dirs
shopt -s nullglob
for d in /opt/epcview-*; do
    remove_path "$d"
done
shopt -u nullglob

# 2. /etc/epcview (system config)
remove_path "/etc/epcview"

# 3. Launcher
remove_path "/usr/local/bin/epcview"

# 4. Per-user config and systemd unit (only the user who ran sudo)
if [[ -n "${SUDO_USER:-}" ]]; then
    user_home=$(getent passwd "$SUDO_USER" | cut -d: -f6 || true)
    if [[ -n "$user_home" ]]; then
        remove_path "$user_home/.config/epcview"
        remove_path "$user_home/.config/systemd/user/epcview.service"
    fi
fi

# 5. The uninstaller itself, last (so the script can finish reading from disk)
SELF="/usr/local/sbin/epcview-uninstall"
if [[ -e "$SELF" ]]; then
    rm -f "$SELF"
    echo "  - removed $SELF"
    removed_anything=1
fi

echo
if [[ $removed_anything -eq 0 ]]; then
    echo "  No epcview installation found — nothing to remove."
else
    echo "✔ epcview removed."
    if [[ -n "${SUDO_USER:-}" ]]; then
        echo
        echo "  Note: only $SUDO_USER's ~/.config/epcview was cleared."
        echo "  Other users' per-user configs (if any) need manual removal."
    fi
fi
