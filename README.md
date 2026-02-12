# SleepAlert

Simple macOS battery monitor that dims/flashes the display at low battery thresholds.

## Behavior by Battery Level

Only applies while running on battery power:

- `5%`: set brightness to `80%` + quick flash alert
- `4%`: set brightness to `60%` + quick flash alert
- `3%`: set brightness to `40%` + quick flash alert
- `2%` and below: continuous flashing

When power is connected again (or battery recovers above low thresholds), the monitor restores the original brightness.

## This Mac (tested)

- macOS 15.5 (24F74)
- Apple M4 Max

## Brightness Tool Note

This setup uses the `brightness` CLI from source (`/usr/local/bin/brightness`).
Repository: [nriley/brightness](https://github.com/nriley/brightness)

Homebrew `brightness` did not work reliably for this machine/context. Follow the guidance from this comment:
[nriley/brightness issue #38 comment](https://github.com/nriley/brightness/issues/38#issuecomment-1033348425)

Recommended steps:

```bash
git clone https://github.com/nriley/brightness.git
cd brightness
make
sudo make install
```

## Run

```bash
./install.sh
```

Manual test:

```bash
SLEEPALERT_TEST_BATTERY_LEVEL=5 python3 -u battery_monitor.py
```
