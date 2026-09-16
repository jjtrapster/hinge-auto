"""Thin wrapper around `adb` commands."""

import random
import re
import shlex
import subprocess
import time

import config

HINGE_PACKAGE = "co.hinge.app"

# Serial chosen by check_device(); every later command is pinned to it so
# a phone and an emulator can be attached at the same time.
_SERIAL: str | None = None


def _run(args: list[str], capture: bool = False) -> bytes | None:
    cmd = ["adb"]
    if _SERIAL:
        cmd += ["-s", _SERIAL]
    cmd += args
    if capture:
        result = subprocess.run(cmd, capture_output=True, check=True)
        return result.stdout
    subprocess.run(cmd, check=True)
    return None


def _shell(args: list[str]) -> str:
    return _run(["shell"] + args, capture=True).decode(errors="replace")


def check_device() -> str:
    """Pick a device, pin all later commands to it, and return its serial.

    Prefers a physical device over an emulator when both are attached.
    """
    global _SERIAL
    out = _run(["devices"], capture=True).decode()
    rows = [l.split("\t") for l in out.splitlines()[1:] if "\t" in l]
    ready = [serial for serial, state in rows if state.strip() == "device"]
    if not ready:
        unauthorized = [s for s, state in rows if state.strip() == "unauthorized"]
        if unauthorized:
            raise RuntimeError(
                f"Device {unauthorized[0]} is attached but unauthorized. "
                "Accept the 'Allow USB debugging' prompt on the phone."
            )
        raise RuntimeError(
            "No ADB device found. Plug in a phone with USB debugging enabled "
            "(or start an emulator) and check `adb devices`."
        )
    physical = [s for s in ready if not s.startswith("emulator-")]
    _SERIAL = (physical or ready)[0]
    return _SERIAL


def screen_size() -> tuple[int, int]:
    """Current logical screen size. Honors a `wm size` override if set."""
    out = _shell(["wm", "size"])
    m = (re.search(r"Override size:\s*(\d+)x(\d+)", out)
         or re.search(r"Physical size:\s*(\d+)x(\d+)", out))
    if not m:
        raise RuntimeError(f"Couldn't parse `wm size` output: {out!r}")
    return int(m.group(1)), int(m.group(2))


def keep_awake() -> None:
    """Keep the screen on while the device is plugged in."""
    _run(["shell", "svc", "power", "stayon", "true"])


def screen_on() -> bool:
    return "mWakefulness=Awake" in _shell(["dumpsys", "power"])


def keyguard_showing() -> bool | None:
    """True if the lock screen is up; None if the dump format is unrecognized."""
    out = _shell(["dumpsys", "window"])
    m = re.search(r"(?:isStatusBarKeyguard|mDreamingLockscreen|mShowingLockscreen)=(true|false)", out)
    return None if m is None else m.group(1) == "true"


def foreground_package() -> str | None:
    out = _shell(["dumpsys", "activity", "activities"])
    m = re.search(r"(?:topResumedActivity|mResumedActivity)[^\n]*?\s([\w.]+)/", out)
    return m.group(1) if m else None


def preflight() -> None:
    """Refuse to start tapping unless the device looks ready for the loop."""
    w, h = screen_size()
    print(f"Screen:   {w}x{h}")
    if (w, h) != (config.SCREEN_WIDTH, config.SCREEN_HEIGHT):
        print(f"WARN: config expects {config.SCREEN_WIDTH}x{config.SCREEN_HEIGHT}. "
              "COORDS and vision thresholds will be off — run calibrate.py "
              "and update config.py.")
    keep_awake()
    if not screen_on():
        raise RuntimeError("Screen is off. Wake and unlock the phone, then re-run.")
    if keyguard_showing():
        raise RuntimeError("Phone is locked. Unlock it, then re-run.")
    pkg = foreground_package()
    if pkg and pkg != HINGE_PACKAGE:
        raise RuntimeError(
            f"Foreground app is {pkg}, not Hinge. Open Hinge on the Discover tab."
        )


def screenshot() -> bytes:
    """Return PNG bytes of the current screen."""
    return _run(["exec-out", "screencap", "-p"], capture=True)


def tap(x: int, y: int) -> None:
    _run(["shell", "input", "tap", str(x), str(y)])


def double_tap(x: int, y: int) -> None:
    """Two taps inside Android's 300 ms double-tap window.

    Issued as one device-side shell line: two separate adb round-trips
    are too slow on a low-end phone and register as two single taps.
    Measured 0.15 s end-to-end on the A05.
    """
    _run(["shell", f"input tap {x} {y} && input tap {x} {y}"])


def back() -> None:
    _run(["shell", "input", "keyevent", "KEYCODE_BACK"])


def keyboard_shown() -> bool:
    return "mInputShown=true" in _shell(["dumpsys", "input_method"])


def input_text(text: str) -> None:
    """Type `text` into the currently focused field via `adb shell input text`.

    Single-quotes the payload with shlex so $, `, ", and spaces survive the
    device shell. Caller should keep text plain ASCII — emoji and the chars
    \\ " $ ` should be filtered upstream (the model is instructed to avoid
    them) since `input text` itself only sends keyevents.
    """
    quoted = shlex.quote(text)
    _run(["shell", f"input text {quoted}"])


def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
    _run(["shell", "input", "swipe",
          str(x1), str(y1), str(x2), str(y2), str(duration_ms)])


def _jitter(v: int, amount: int) -> int:
    return v + random.randint(-amount, amount)


def _scroll(direction: int) -> None:
    """One randomised scroll gesture. direction=+1 scrolls the content
    down (finger swipes up), -1 scrolls up. Start/end points and duration
    are jittered per call (config.SCROLL_JITTER) so no two swipes match."""
    c, j = config.COORDS, config.SCROLL_JITTER
    x_from = _jitter(c["scroll_from"][0], j["x_px"])
    x_to = _jitter(c["scroll_to"][0], j["x_px"])
    y_from = _jitter(c["scroll_from"][1], j["y_px"])
    y_to = _jitter(c["scroll_to"][1], j["y_px"])
    pct = j["duration_pct"]
    duration = int(c["scroll_duration_ms"] * random.uniform(1 - pct, 1 + pct))
    if direction > 0:
        swipe(x_from, y_from, x_to, y_to, duration)
    else:
        swipe(x_to, y_to, x_from, y_from, duration)


def scroll_down() -> None:
    _scroll(+1)


def scroll_up() -> None:
    _scroll(-1)


def jitter_sleep(key: str) -> None:
    lo, hi = config.DELAYS[key]
    time.sleep(random.uniform(lo, hi))
