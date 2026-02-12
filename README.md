# SleepAlert

Simple macOS battery monitor that dims/flashes the display at low battery thresholds.

## This Mac (tested)

- macOS 15.5 (24F74)
- Apple M4 Max

## Brightness Tool Note

This setup uses the `brightness` CLI from source (`/usr/local/bin/brightness`).

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
