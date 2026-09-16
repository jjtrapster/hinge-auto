"""Configuration for HingeAuto.

PREFERENCES, AGE_MIN/MAX, and MESSAGE_VOICE come from the active mode (see
`modes/`). Set ACTIVE_MODE here for the persistent default; override per-run
via `python main.py --mode <name>`.

The COORDS defaults below are calibrated for a Samsung Galaxy A05 (720x1600,
3-button nav) against the Hinge layout as of September 2026. If that's what
you're running and Hinge hasn't shifted its layout, they should work as-is.
Otherwise run `python calibrate.py` and update the values that don't match
your device.
"""

from pathlib import Path

# ---------- Mode selection ----------
# Which `modes/<name>.py` to load. Overridden per-run by `python main.py --mode X`.
ACTIVE_MODE = "twenty_somethings"

# These get filled in by _apply_mode() at the bottom of this file. Declared
# here so static analyzers / IDEs see them. Do not edit by hand — edit the
# mode module instead.
PREFERENCES: str = ""
AGE_MIN: int | None = None
AGE_MAX: int | None = None
MESSAGE_VOICE: str | None = None
MODE_NAME: str = ""
PREMADES: list[dict] = []
JUDGE_FRAMES: int | None = None      # send only the first N captured frames to the judge
FORCE_PREMADE_ID: str | None = None  # every like sends this premade, whatever the model wrote
SKIP_NEEDS_HIGH_CONFIDENCE: bool = False  # a skip below "high" confidence becomes a like

# ---------- Run mode ----------
# DRY_RUN = False -> actually like / send messages (default)
# DRY_RUN = True  -> decide and log, but force-skip every profile
#                    instead of liking. Every "would-like" profile gets
#                    skipped (gone from your queue) but no likes are
#                    spent.
#
# When to flip this to True:
#   - Free Hinge (8 likes/day): YES, for your first run or two. Lets
#     you watch decisions without spending your daily cap on a rubric
#     you haven't tuned. Once decisions look right, flip back to False.
#   - Hinge+ (unlimited likes): NO. Just run small live batches
#     (MAX_LIKES_PER_SESSION = 5) and Ctrl-C if something looks off.
DRY_RUN = False

# Default = 8, which matches free-tier Hinge's daily like cap (resets at
# 4am local). One session per day exhausts the free allotment cleanly.
#
# If you have Hinge+ (no daily cap), bump this to ~25-50 per session and
# run multiple sessions throughout the day. Going much higher per session
# tends to trigger Hinge's soft-throttle (empty Discover after a burst);
# spacing batches across the day works better than one giant batch.
MAX_LIKES_PER_SESSION = 8
MAX_PROFILES_PER_SESSION = 100

# ---------- Device settings ----------
# Samsung Galaxy A05 (SM-A055F): 720x1600 @ 300 dpi, 3-button navigation.
# main.py reads the real size from the device at startup (`adb shell wm
# size`) and warns if it differs. Change these to match your phone and
# re-run calibrate.py. vision.py scales its pixel thresholds by
# SCREEN_WIDTH / 720.
SCREEN_WIDTH = 720
SCREEN_HEIGHT = 1600

# Number of scroll-and-screenshot passes per profile.
# Longer profiles (6 photos + 3 prompts) need ~7 frames at the scroll step
# below. Duplicate end frames on shorter profiles are harmless.
FRAMES_PER_PROFILE = 7

# ---------- Coordinates ----------
# Galaxy A05 (720x1600, 3-button nav) against the Hinge layout as of
# 2026-09: the skip X is a fixed floating button bottom-left; hearts are
# dark circles at the bottom-right of each photo/prompt card; tapping a
# heart expands that card inline into a compose card (comment field,
# Rose, Send Like) rather than opening a sheet. If anything is off, run
# `python calibrate.py` and update the values that don't match.
COORDS = {
    # Skip / like action targets (Discover screen, photo 1 at top)
    "skip_button":       (95, 1301),    # floating X, same spot in every frame
    "heart_photo_1":     (617, 895),    # heart on photo 1 when scrolled to top

    # Inline compose card. Fallbacks only — vision.py re-finds them at
    # tap-time because the card sits wherever the tapped heart was.
    "send_like_button":  (465, 836),
    "comment_input":     (360, 720),

    # Scroll gesture (swipe up = scroll down through profile). One swipe
    # travels ~600-900 px with momentum; 7 frames cover a full profile.
    "scroll_from":       (360, 1150),
    "scroll_to":         (360, 450),
    "scroll_duration_ms": 300,       # centre value; see SCROLL_JITTER

    # Bottom nav (5 evenly-spaced icons, band y 1397-1510).
    "nav_discover":      (72, 1453),
    "nav_standouts":     (216, 1453),
    "nav_likes_you":     (360, 1453),
    "nav_matches":       (504, 1453),
    "nav_self_pfp":      (648, 1453),

    # Self-profile flow (used by scan_self.py — "what does my profile
    # look like to others"). From Discover: nav_self_pfp → self_avatar →
    # view_tab gets you to a scrollable view of your own profile. Then
    # back_arrow → back_arrow → nav_discover to return.
    # UNCALIBRATED on the A05 — scaled 2/3 from the Pixel values. Verify
    # with calibrate.py before running scan_self.py.
    "self_avatar":       (360, 331),
    "view_tab":          (540, 207),
    "back_arrow":        (43, 133),

    # Discover filter row (tap the chip to open its bottom sheet).
    "sliders_icon":      (65, 120),     # opens Dating Preferences
    "age_chip":          (174, 120),    # opens Age filter sheet
}

# ---------- Timing ----------
# Scroll gesture randomisation: each swipe's start and end points move by
# up to +/- x_px / y_px and its duration by +/- duration_pct, so no two
# swipes are pixel-identical.
SCROLL_JITTER = {"x_px": 40, "y_px": 60, "duration_pct": 0.25}

# Random delay between actions (seconds, min/max for jitter).
DELAYS = {
    "after_scroll":     (0.4, 0.75),
    "after_screenshot": (0.2, 0.4),
    "after_tap":        (0.8, 1.4),
    "after_like_sent":  (2.5, 4.0),
    "after_skip":       (1.5, 2.5),
}

# ---------- Judge backend ----------
# "anthropic" -> uses your ANTHROPIC_API_KEY; best quality, ~$0.02-0.05/profile.
# "ollama"    -> uses Ollama Cloud (free tier) or local Ollama; lower quality
#                but no per-token cost.
JUDGE_BACKEND = "ollama"

# ---------- Anthropic settings (when JUDGE_BACKEND == "anthropic") ----------
# Sonnet is the default — cheaper than Opus and plenty capable for this task.
# Switch to "claude-opus-4-7" if you want top-quality judgment, or
# "claude-haiku-4-5" for cheapest (may miss subtle cues).
MODEL = "claude-sonnet-4-6"
EFFORT = "medium"  # low | medium | high

# ---------- Ollama settings (when JUDGE_BACKEND == "ollama") ----------
# Vision-capable models that handle multiple images per turn:
#   "qwen2.5vl"        — strong all-around vision model (recommended)
#   "qwen2.5vl:7b"     — smaller, faster, weaker
#   "llama3.2-vision"   — alternative; tool-calling can be flakier
OLLAMA_MODEL = "qwen2.5vl"

# Downscale frames before sending them to Ollama. Image tokens scale with
# pixel count, so 0.5 is ~4x fewer tokens and ~4x faster per profile
# (measured 161s -> 41s for 7 frames of qwen2.5vl on a 16 GB M-series
# Mac). Profile text is still legible at half res. 1.0 = send full-res.
OLLAMA_FRAME_SCALE = 0.5

# Context window. Ollama defaults to 4096, but 7 full-res frames plus the
# system prompt run ~15k tokens (~5.5k at OLLAMA_FRAME_SCALE = 0.5).
# Raise if you add frames or a long rubric.
OLLAMA_NUM_CTX = 16384

# Hard cap on generated tokens per judgment. A complete submit_decision
# JSON is ~150-300 tokens. Small open models can fall into a repetition
# loop inside a string field, and under constrained JSON decoding they
# then never emit the closing brace — without a cap that runs until the
# context is full (seen on qwen2.5vl: 7k+ tokens, 7+ minutes, no end in
# sight). A loop that hits this cap costs ~25s and is retried by main.py.
OLLAMA_NUM_PREDICT = 400

# Seconds to wait for one judgment before giving up. main.py's retry
# logic takes over from there.
OLLAMA_TIMEOUT = 300

# OLLAMA_HOST: None or "" -> default http://localhost:11434
#              "https://ollama.com" -> Ollama Cloud (requires OLLAMA_API_KEY)
# Can also be set via the OLLAMA_HOST environment variable.
OLLAMA_HOST = None

# ---------- Paths ----------
BASE_DIR = Path(__file__).parent
DEBUG_DIR = BASE_DIR / "debug"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
SAVE_DEBUG_FRAMES = False  # True keeps frames + decisions in debug/ for review
# True appends one JSONL line per judged profile to debug/session_log.jsonl.
# False (default) keeps no record on disk — decisions only appear live on
# screen as they happen.
SAVE_SESSION_LOG = False


def _apply_mode() -> None:
    """Resolve ACTIVE_MODE and populate this module's PREFERENCES /
    AGE_MIN / AGE_MAX / MESSAGE_VOICE / MODE_NAME / cap overrides.

    Re-entrant — main.py calls this again after parsing --mode so a CLI
    override takes effect before the judge sees config.
    """
    import modes
    mode = modes.load(ACTIVE_MODE)
    g = globals()
    g["PREFERENCES"] = mode.PREFERENCES
    g["AGE_MIN"] = getattr(mode, "AGE_MIN", None)
    g["AGE_MAX"] = getattr(mode, "AGE_MAX", None)
    g["MESSAGE_VOICE"] = getattr(mode, "MESSAGE_VOICE", None)
    g["MODE_NAME"] = mode.NAME
    g["PREMADES"] = list(getattr(mode, "PREMADES", []))
    g["JUDGE_FRAMES"] = getattr(mode, "JUDGE_FRAMES", None)
    g["FORCE_PREMADE_ID"] = getattr(mode, "FORCE_PREMADE_ID", None)
    g["SKIP_NEEDS_HIGH_CONFIDENCE"] = bool(getattr(mode, "SKIP_NEEDS_HIGH_CONFIDENCE", False))
    if g["FORCE_PREMADE_ID"] and g["FORCE_PREMADE_ID"] not in {p["id"] for p in g["PREMADES"]}:
        raise ValueError(
            f"mode {mode.NAME!r}: FORCE_PREMADE_ID={g['FORCE_PREMADE_ID']!r} "
            "is not an id in its PREMADES"
        )
    for k in ("MAX_LIKES_PER_SESSION", "MAX_PROFILES_PER_SESSION"):
        v = getattr(mode, k, None)
        if v is not None:
            g[k] = v


_apply_mode()
