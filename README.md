# Sleep Alert - Battery Monitor

A background app that helps you remember to charge your device by providing visual alerts as battery drains.

## Features

- Monitors battery level continuously (only when unplugged)
- **5%**: Dims to 80% brightness + quick flash alert
- **4%**: Dims to 60% brightness + quick flash alert
- **3%**: Dims to 40% brightness + quick flash alert
- **2% and below**: Continuous annoying screen flashing until you plug in!
- Automatically restores brightness when plugged in or battery recovers

## Quick Install

Run the install script to set it up as a background service:
```bash
./install.sh
```

This will install the battery monitor to run automatically in the background and start on login.

## Manual Usage

Run the script manually:
```bash
python3 battery_monitor.py
```

The app will run in the foreground and print status updates. Press Ctrl+C to stop.

### Simulate Battery Levels (Test Mode)

To test low-battery behavior instantly, simulate battery percentage:
```bash
SLEEPALERT_TEST_BATTERY_LEVEL=5 python3 battery_monitor.py
```

Other useful tests:
```bash
SLEEPALERT_TEST_BATTERY_LEVEL=4 python3 battery_monitor.py
SLEEPALERT_TEST_BATTERY_LEVEL=3 python3 battery_monitor.py
SLEEPALERT_TEST_BATTERY_LEVEL=2 python3 battery_monitor.py
```

By default, simulated battery mode behaves as `on battery` (unplugged) so alerts run even if you are charging.

Optional: force simulated plugged state:
```bash
SLEEPALERT_TEST_BATTERY_LEVEL=3 SLEEPALERT_TEST_PLUGGED_IN=1 python3 battery_monitor.py
```

Optional brightness-trigger test (separate test hook):
```bash
SLEEPALERT_TEST_BRIGHTNESS_CUTOFF=0.70 python3 battery_monitor.py
```

When current brightness drops to or below that cutoff, the app triggers the same dim + flash sequence as the real 3% battery path.

## Uninstall

To remove the background service:
```bash
./uninstall.sh
```

## Logs

When running as a background service, logs are saved to:
- `~/Library/Application Support/SleepAlert/battery_monitor.log` - Status updates
- `~/Library/Application Support/SleepAlert/battery_monitor.error.log` - Errors (if any)

## Troubleshooting

If the service was installed before these fixes, reinstall it so launchd uses the updated script:

```bash
./uninstall.sh
./install.sh
```

## Requirements

- macOS
- Python 3
- Accessibility permissions may be required for brightness control
