#!/bin/bash
# Uninstall script for Sleep Alert battery monitor
set -euo pipefail

PLIST_NAME="com.sleepalert.batterymonitor.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
APP_SUPPORT_DIR="$HOME/Library/Application Support/SleepAlert"
AGENT_PLIST="$LAUNCH_AGENTS_DIR/$PLIST_NAME"
GUI_UID="gui/$(id -u)"

echo "Uninstalling Sleep Alert battery monitor..."

# Unload the launch agent
launchctl bootout "$GUI_UID/$PLIST_NAME" 2>/dev/null || true

# Remove the plist file
rm -f "$AGENT_PLIST"

# Remove the app directory
rm -rf "$APP_SUPPORT_DIR"

echo "✓ Uninstall complete!"
echo ""
echo "The battery monitor has been stopped and removed from startup."
