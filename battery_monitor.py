#!/usr/bin/env python3
"""
Battery Monitor - Visual alerts for low battery levels
Monitors battery percentage and provides visual feedback:
- 5% to 3%: Gradual dimming + quick flash alerts
- 2% and below: Continuous flashing
"""

import subprocess
import time
import sys
import platform
import re
import os
import shutil
import ctypes
import ctypes.util
from ctypes import byref, c_char_p, c_float, c_uint32, c_void_p


_CFSTRING_ENCODING_UTF8 = 0x08000100
TEST_BRIGHTNESS_CUTOFF_ENV = "SLEEPALERT_TEST_BRIGHTNESS_CUTOFF"
TEST_BATTERY_LEVEL_ENV = "SLEEPALERT_TEST_BATTERY_LEVEL"
TEST_PLUGGED_ENV = "SLEEPALERT_TEST_PLUGGED_IN"


def get_test_brightness_cutoff():
    """Read optional test cutoff from env var (0.0 to 1.0)."""
    raw = os.getenv(TEST_BRIGHTNESS_CUTOFF_ENV)
    if raw is None:
        return None
    try:
        value = float(raw)
        if 0.0 <= value <= 1.0:
            return value
    except ValueError:
        pass
    print(f"Invalid {TEST_BRIGHTNESS_CUTOFF_ENV} value '{raw}', expected 0.0-1.0")
    return None


def get_test_battery_override():
    """Read optional simulated battery settings from env vars."""
    raw_level = os.getenv(TEST_BATTERY_LEVEL_ENV)
    if raw_level is None:
        return None

    try:
        level = int(raw_level)
        if not 0 <= level <= 100:
            raise ValueError
    except ValueError:
        print(f"Invalid {TEST_BATTERY_LEVEL_ENV} value '{raw_level}', expected integer 0-100")
        return None

    # Default test behavior: act as unplugged so low-battery effects can be tested while charging.
    plugged_raw = os.getenv(TEST_PLUGGED_ENV, "0").strip().lower()
    plugged = plugged_raw in {"1", "true", "yes", "on"}
    return level, plugged


def _load_display_libraries():
    """Load macOS frameworks needed for brightness control."""
    try:
        core_graphics = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))
        iokit = ctypes.CDLL(ctypes.util.find_library("IOKit"))
        core_foundation = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))

        core_graphics.CGMainDisplayID.restype = c_uint32
        core_graphics.CGDisplayIOServicePort.argtypes = [c_uint32]
        core_graphics.CGDisplayIOServicePort.restype = c_uint32

        core_foundation.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_uint32]
        core_foundation.CFStringCreateWithCString.restype = c_void_p

        iokit.IODisplayGetFloatParameter.argtypes = [c_uint32, c_uint32, c_void_p, ctypes.POINTER(c_float)]
        iokit.IODisplayGetFloatParameter.restype = ctypes.c_int
        iokit.IODisplaySetFloatParameter.argtypes = [c_uint32, c_uint32, c_void_p, c_float]
        iokit.IODisplaySetFloatParameter.restype = ctypes.c_int

        return core_graphics, iokit, core_foundation
    except Exception:
        return None, None, None


def _load_display_services():
    """Load private DisplayServices framework as fallback brightness backend."""
    try:
        display_services = ctypes.CDLL(
            "/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices"
        )
        display_services.DisplayServicesGetBrightness.argtypes = [c_uint32, ctypes.POINTER(c_float)]
        display_services.DisplayServicesGetBrightness.restype = ctypes.c_int
        display_services.DisplayServicesSetBrightness.argtypes = [c_uint32, c_float]
        display_services.DisplayServicesSetBrightness.restype = ctypes.c_int
        return display_services
    except Exception:
        return None


def _find_brightness_cli():
    """Find brightness CLI in PATH or common install locations."""
    cli = shutil.which("brightness")
    if cli:
        return cli
    for candidate in ("/usr/local/bin/brightness", "/opt/homebrew/bin/brightness"):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


_CORE_GRAPHICS, _IOKIT, _CORE_FOUNDATION = _load_display_libraries()
_DISPLAY_SERVICES = _load_display_services()
_BRIGHTNESS_CLI = _find_brightness_cli()
_BRIGHTNESS_KEY = None
_LAST_BRIGHTNESS = None
_WARNED_BRIGHTNESS_CONTROL = False
_WARNED_BRIGHTNESS_CLI = False
_LOGGED_BRIGHTNESS_BACKEND = None


def _get_brightness_key():
    """Create CFStringRef for 'brightness' once."""
    global _BRIGHTNESS_KEY
    if _BRIGHTNESS_KEY is not None or _CORE_FOUNDATION is None:
        return _BRIGHTNESS_KEY
    _BRIGHTNESS_KEY = _CORE_FOUNDATION.CFStringCreateWithCString(None, b"brightness", _CFSTRING_ENCODING_UTF8)
    return _BRIGHTNESS_KEY


def _get_display_service():
    """Return the IOKit service handle for the main display."""
    if _CORE_GRAPHICS is None:
        return 0
    display_id = _CORE_GRAPHICS.CGMainDisplayID()
    if display_id == 0:
        return 0
    return _CORE_GRAPHICS.CGDisplayIOServicePort(display_id)


def _get_main_display_id():
    """Return the main display id, or 0 when unavailable."""
    if _CORE_GRAPHICS is None:
        return 0
    return _CORE_GRAPHICS.CGMainDisplayID()


def _warn_brightness_unavailable():
    """Log a single warning when no brightness backend is available."""
    global _WARNED_BRIGHTNESS_CONTROL
    if _WARNED_BRIGHTNESS_CONTROL:
        return
    print(
        "Warning: brightness control unavailable on this display/session; "
        "alerts will run but brightness changes may not apply."
    )
    _WARNED_BRIGHTNESS_CONTROL = True


def _warn_brightness_cli(message):
    """Log a single warning when brightness CLI exists but fails."""
    global _WARNED_BRIGHTNESS_CLI
    if _WARNED_BRIGHTNESS_CLI:
        return
    print(f"Warning: brightness CLI failed ({message}); falling back to API backends.")
    _WARNED_BRIGHTNESS_CLI = True


def _log_brightness_backend(name):
    """Log backend selection once."""
    global _LOGGED_BRIGHTNESS_BACKEND
    if _LOGGED_BRIGHTNESS_BACKEND == name:
        return
    print(f"Brightness backend: {name}")
    _LOGGED_BRIGHTNESS_BACKEND = name


def _get_brightness_via_cli():
    """Get brightness via external brightness utility."""
    if _BRIGHTNESS_CLI is None:
        return None
    try:
        result = subprocess.run(
            [_BRIGHTNESS_CLI, "-l"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception as e:
        _warn_brightness_cli(str(e))
        return None

    output = f"{result.stdout}\n{result.stderr}".strip()
    if result.returncode != 0:
        _warn_brightness_cli(output or f"exit code {result.returncode}")
        return None

    matches = re.findall(r'brightness[^0-9]*([0-9]*\.?[0-9]+)', output, flags=re.IGNORECASE)
    if not matches:
        if output:
            _warn_brightness_cli(f"unrecognized output: {output}")
        return None

    try:
        return max(0.0, min(1.0, float(matches[0])))
    except ValueError:
        _warn_brightness_cli(f"invalid numeric output: {matches[0]}")
        return None


def _set_brightness_via_cli(level):
    """Set brightness via external brightness utility."""
    if _BRIGHTNESS_CLI is None:
        return False
    try:
        result = subprocess.run(
            [_BRIGHTNESS_CLI, f"{level:.4f}"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception as e:
        _warn_brightness_cli(str(e))
        return False

    if result.returncode == 0:
        return True

    output = f"{result.stdout}\n{result.stderr}".strip()
    _warn_brightness_cli(output or f"exit code {result.returncode}")
    return False

def get_battery_info():
    """Get current battery percentage and charging status on macOS"""
    try:
        result = subprocess.run(
            ['pmset', '-g', 'batt'],
            capture_output=True,
            text=True,
            check=True
        )
        # Parse output like "Now drawing from 'Battery Power' -InternalBattery-0 (id=12345) 85%; discharging; 2:30 remaining"
        # or "Now drawing from 'AC Power' -InternalBattery-0 (id=12345) 85%; charging; 1:30 remaining present: true"

        is_plugged_in = "'AC Power'" in result.stdout

        battery_match = re.search(r'(\d+)%', result.stdout)
        if battery_match:
            return int(battery_match.group(1)), is_plugged_in

        return None, is_plugged_in
    except Exception as e:
        print(f"Error getting battery info: {e}")
        return None, False

def get_current_brightness():
    """Get current screen brightness (0.0 to 1.0)"""
    global _LAST_BRIGHTNESS
    try:
        brightness_cli_value = _get_brightness_via_cli()
        if brightness_cli_value is not None:
            _LAST_BRIGHTNESS = brightness_cli_value
            _log_brightness_backend(f"brightness CLI ({_BRIGHTNESS_CLI})")
            return brightness_cli_value

        service = _get_display_service()
        key = _get_brightness_key()
        if service != 0 and key is not None and _IOKIT is not None:
            brightness = c_float(0.0)
            status = _IOKIT.IODisplayGetFloatParameter(service, 0, key, byref(brightness))
            if status == 0:
                value = max(0.0, min(1.0, float(brightness.value)))
                _LAST_BRIGHTNESS = value
                _log_brightness_backend("IOKit")
                return value

        display_id = _get_main_display_id()
        if display_id != 0 and _DISPLAY_SERVICES is not None:
            brightness = c_float(0.0)
            status = _DISPLAY_SERVICES.DisplayServicesGetBrightness(display_id, byref(brightness))
            if status == 0:
                value = max(0.0, min(1.0, float(brightness.value)))
                _LAST_BRIGHTNESS = value
                _log_brightness_backend("DisplayServices")
                return value
    except Exception as e:
        print(f"Error getting brightness: {e}")
    if _BRIGHTNESS_CLI is not None:
        # Some brightness builds can set values but provide no parsable listing output.
        if _LAST_BRIGHTNESS is not None:
            return _LAST_BRIGHTNESS
        return 0.5
    if _LAST_BRIGHTNESS is not None:
        return _LAST_BRIGHTNESS
    _warn_brightness_unavailable()
    return 0.5  # Default fallback

def set_brightness(level):
    """Set screen brightness (0.0 to 1.0)"""
    global _LAST_BRIGHTNESS
    try:
        clamped_level = max(0.0, min(1.0, float(level)))

        if _set_brightness_via_cli(clamped_level):
            _LAST_BRIGHTNESS = clamped_level
            _log_brightness_backend(f"brightness CLI ({_BRIGHTNESS_CLI})")
            return

        service = _get_display_service()
        key = _get_brightness_key()
        if service != 0 and key is not None and _IOKIT is not None:
            status = _IOKIT.IODisplaySetFloatParameter(service, 0, key, c_float(clamped_level))
            if status == 0:
                _LAST_BRIGHTNESS = clamped_level
                _log_brightness_backend("IOKit")
                return
            print(f"Error setting brightness: IOKit returned status {status}")

        display_id = _get_main_display_id()
        if display_id != 0 and _DISPLAY_SERVICES is not None:
            status = _DISPLAY_SERVICES.DisplayServicesSetBrightness(display_id, c_float(clamped_level))
            if status == 0:
                _LAST_BRIGHTNESS = clamped_level
                _log_brightness_backend("DisplayServices")
                return
            print(f"Error setting brightness: DisplayServices returned status {status}")

        _warn_brightness_unavailable()
    except Exception as e:
        print(f"Error setting brightness: {e}")

def flash_screen(duration=0.3):
    """Flash the screen by toggling brightness"""
    original = get_current_brightness()
    set_brightness(0.0)
    time.sleep(duration)
    set_brightness(original)
    time.sleep(duration)

def quick_flash(count=2, duration=0.15):
    """Do a few quick flashes"""
    original = get_current_brightness()
    for _ in range(count):
        set_brightness(0.0)
        time.sleep(duration)
        set_brightness(original)
        time.sleep(duration)

def monitor_battery():
    """Main monitoring loop"""
    print("Battery Monitor Started")
    print("Monitoring battery levels...")
    print("Press Ctrl+C to stop")

    last_battery = None
    last_plugged_status = None
    original_brightness = None
    brightness_was_modified = False
    check_interval = 10  # Check every 10 seconds
    test_brightness_cutoff = get_test_brightness_cutoff()
    test_battery_override = get_test_battery_override()
    test_trigger_armed = True

    if test_brightness_cutoff is not None:
        print(f"Test mode: brightness cutoff {test_brightness_cutoff:.2f} enabled (mimics 3% behavior)")
    if test_battery_override is not None:
        level, plugged = test_battery_override
        power_state = "plugged in" if plugged else "on battery"
        print(f"Test mode: simulating battery at {level}% ({power_state})")

    try:
        while True:
            battery, is_plugged_in = get_battery_info()
            if test_battery_override is not None:
                battery, is_plugged_in = test_battery_override

            if battery is None:
                print("Unable to read battery level")
                time.sleep(check_interval)
                continue

            # Print status when battery level or plugged status changes
            if battery != last_battery or is_plugged_in != last_plugged_status:
                status = "plugged in" if is_plugged_in else "on battery"
                print(f"Battery: {battery}% ({status})")
                last_battery = battery
                last_plugged_status = is_plugged_in

            # Save original brightness on first run
            if original_brightness is None:
                original_brightness = get_current_brightness()

            current_brightness = get_current_brightness()
            test_triggered = (
                test_brightness_cutoff is not None
                and test_trigger_armed
                and current_brightness <= test_brightness_cutoff
            )
            if (
                test_brightness_cutoff is not None
                and current_brightness > test_brightness_cutoff
            ):
                test_trigger_armed = True

            # If plugged in, restore brightness if it was modified
            if is_plugged_in:
                if brightness_was_modified:
                    print("Device plugged in, restoring brightness")
                    if original_brightness:
                        set_brightness(original_brightness)
                    brightness_was_modified = False
                time.sleep(check_interval)
                continue

            # Only apply visual effects when NOT plugged in
            if test_triggered:
                print(
                    f"⚠️  TEST: brightness {current_brightness:.2f} <= {test_brightness_cutoff:.2f} - "
                    "mimicking 3% cutoff"
                )
                set_brightness(0.4)
                quick_flash()
                brightness_was_modified = True
                test_trigger_armed = False
                time.sleep(check_interval)
            elif battery <= 2:
                # Continuous flashing at 2% and below
                print(f"⚠️  CRITICAL: {battery}% battery - FLASHING SCREEN")
                # Flash continuously during the check interval
                flash_duration = 0.3
                flashes = int(check_interval / (flash_duration * 2))
                for _ in range(flashes):
                    flash_screen(duration=flash_duration)
                brightness_was_modified = True
            elif battery == 3:
                print("⚠️  WARNING: 3% battery - Dimming + flash alert")
                set_brightness(0.4)
                quick_flash()
                brightness_was_modified = True
                time.sleep(check_interval)
            elif battery == 4:
                print("⚠️  WARNING: 4% battery - Slight dim + flash alert")
                set_brightness(0.6)
                quick_flash()
                brightness_was_modified = True
                time.sleep(check_interval)
            elif battery == 5:
                print("⚠️  LOW: 5% battery - Starting to dim + flash alert")
                set_brightness(0.8)
                quick_flash()
                brightness_was_modified = True
                time.sleep(check_interval)
            else:
                # Reset brightness if above threshold
                if brightness_was_modified and battery > 5:
                    print("Battery level recovered, restoring brightness")
                    if original_brightness:
                        set_brightness(original_brightness)
                    brightness_was_modified = False
                time.sleep(check_interval)

    except KeyboardInterrupt:
        print("\nStopping battery monitor...")
        # Restore brightness on exit
        if original_brightness:
            print("Restoring original brightness...")
            set_brightness(original_brightness)
        sys.exit(0)

if __name__ == "__main__":
    if platform.system() != "Darwin":
        print("This script is designed for macOS only")
        sys.exit(1)

    monitor_battery()
