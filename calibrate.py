"""Saves a screenshot so you can read pixel coords for config.COORDS.

Open the resulting PNG in any image viewer that shows cursor position
(MS Paint, IrfanView, etc.) and hover over each UI element you need
to record.
"""

from pathlib import Path

import adb


def main() -> None:
    adb.check_device()
    path = Path(__file__).parent / "calibrate.png"
    path.write_bytes(adb.screenshot())
    print(f"Saved: {path}")
    print()
    print("Open the file and read pixel coords for:")
    print("  1. Skip (X) button         -> COORDS['skip_button']")
    print("  2. Heart on first photo    -> COORDS['heart_photo_1']")
    print("     (scroll Hinge to the top before screenshotting)")
    print("  3. 'Send Like' button      -> COORDS['send_like_button']")
    print("     (tap a heart first to expand the compose card, then re-run")
    print("      this script; switch tabs Standouts -> Discover to dismiss it)")
    print("  4. Bottom nav icons        -> COORDS['nav_*']")
    print("  5. Filter chips            -> COORDS['sliders_icon'], ['age_chip']")
    print()
    print("Then edit config.py (and SCREEN_WIDTH/HEIGHT if they differ).")


if __name__ == "__main__":
    main()
