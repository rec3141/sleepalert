#!/bin/bash
# Install script for Sleep Alert battery monitor
set -euo pipefail

PLIST_NAME="com.sleepalert.batterymonitor.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
APP_SUPPORT_DIR="$HOME/Library/Application Support/SleepAlert"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_PLIST="$LAUNCH_AGENTS_DIR/$PLIST_NAME"
GUI_UID="gui/$(id -u)"

echo "Installing Sleep Alert battery monitor..."

# Create directories if they don't exist
mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$APP_SUPPORT_DIR"

# Copy the script to Application Support
cp "$SCRIPT_DIR/battery_monitor.py" "$APP_SUPPORT_DIR/"
chmod +x "$APP_SUPPORT_DIR/battery_monitor.py"

# Create the plist with correct paths
cat > "$AGENT_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sleepalert.batterymonitor</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>-u</string>
        <string>$APP_SUPPORT_DIR/battery_monitor.py</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>LimitLoadToSessionType</key>
    <array>
        <string>Aqua</string>
    </array>

    <key>StandardOutPath</key>
    <string>$APP_SUPPORT_DIR/battery_monitor.log</string>

    <key>StandardErrorPath</key>
    <string>$APP_SUPPORT_DIR/battery_monitor.error.log</string>

    <key>ProcessType</key>
    <string>Interactive</string>
</dict>
</plist>
EOF

# Reload the launch agent (modern launchctl flow with fallback)
launchctl bootout "$GUI_UID/$PLIST_NAME" 2>/dev/null || true
launchctl bootstrap "$GUI_UID" "$AGENT_PLIST"
launchctl kickstart -k "$GUI_UID/$PLIST_NAME"

echo "✓ Installation complete!"
echo ""
echo "The battery monitor is now running in the background."
echo "It will start automatically when you log in."
echo ""
echo "Logs are saved to:"
echo "  $APP_SUPPORT_DIR/battery_monitor.log"
echo "  $APP_SUPPORT_DIR/battery_monitor.error.log"
echo ""
echo "To uninstall, run: ./uninstall.sh"
