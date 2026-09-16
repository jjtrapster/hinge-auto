"""HingeAuto orchestrator.

Loop: capture profile frames -> ask Claude -> tap like or skip -> repeat.
"""

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

import io

from PIL import Image

import adb
import config
import metrics
import vision
from judge_common import load_backend

judge = load_backend().judge

# Judge errors a retry won't fix, matched as substrings of repr(e). Halting
# beats blindly force-skipping: every skip without a decision burns a
# profile from the queue and looks robotic to Hinge. Saw this once when the
# Anthropic credit balance hit zero mid-run: 124 profiles got blindly
# skipped before anyone noticed.
FATAL_JUDGE_ERRORS = (
    # Anthropic: billing / auth
    "credit balance is too low",
    "authentication_error",
    "invalid_api_key",
    "permission_error",
    # Ollama: server not running, model not pulled
    "Connection refused",
    "ConnectError",
    "ConnectionError",
    "not found, try pulling",
)

# Backstop for failures the substring list doesn't name: if the judge fails
# every attempt on this many profiles in a row, the backend is down in some
# new way — halt rather than keep skipping blind.
MAX_CONSECUTIVE_JUDGE_FAILURES = 2


def _profile_region_hash(png: bytes) -> str:
    """md5 over a cropped region of the frame, excluding status bar (clock
    ticks every minute) and bottom nav (badges flicker). Two screenshots
    of the same profile taken 60+ seconds apart should produce the same
    hash; two different profiles should always differ."""
    img = Image.open(io.BytesIO(png))
    w, h = img.size
    crop = img.crop((0, int(h * 0.05), w, int(h * 0.86)))
    return hashlib.md5(crop.tobytes()).hexdigest()


def capture_profile() -> list[bytes]:
    """Scroll through the current profile, returning a list of PNG frames."""
    # Defensive: new profiles load at the top, so this is just guarding
    # against the app being mid-scroll from a prior partial action. A
    # handful of swipes is enough — full 18-swipe sweep isn't needed
    # because we aren't recovering from a 7-frame scroll-down.
    scroll_back_to_top(swipes=5)

    frames = []
    frames.append(adb.screenshot())
    adb.jitter_sleep("after_screenshot")

    for _ in range(config.FRAMES_PER_PROFILE - 1):
        adb.scroll_down()
        adb.jitter_sleep("after_scroll")
        frames.append(adb.screenshot())
        adb.jitter_sleep("after_screenshot")

    return frames


def scroll_back_to_top(swipes: int | None = None) -> int:
    """Scroll back to the top of the profile. Returns the swipes used.

    Hinge uses momentum scrolling; each swipe's actual travel is much less
    than the gesture's pixel distance. `swipes` is a ceiling — default
    `FRAMES_PER_PROFILE * 2 + 4` (18 with FRAMES=7), enough to recover from
    a full scroll-down through the profile. We stop early as soon as a
    swipe leaves the profile region unchanged, which is what the top looks
    like: a profile already at the top costs one swipe instead of five, a
    full recovery roughly half the ceiling. Animated content that never
    settles just falls through to the ceiling.
    """
    if swipes is None:
        swipes = config.FRAMES_PER_PROFILE * 2 + 4
    before = _profile_region_hash(adb.screenshot())
    for used in range(1, swipes + 1):
        adb.scroll_up()
        adb.jitter_sleep("after_scroll")
        after = _profile_region_hash(adb.screenshot())
        if after == before:
            return used
        before = after
    return swipes


def do_skip() -> None:
    """Tap the X to advance to the next profile. Always taps (even in dry run);
    advancing is needed for the loop to see new profiles."""
    x, y = config.COORDS["skip_button"]
    adb.tap(x, y)
    adb.jitter_sleep("after_skip")


def do_like(message: str = "") -> None:
    """In live mode: scroll to top, tap heart, type message (if any), tap Send Like.
    In dry run: advance by skipping (so we never send an actual like).

    Send Like / comment input positions are found at tap-time via vision —
    the compose card anchors to whichever heart was tapped and shifts per
    profile, so static COORDS don't survive across profiles.
    """
    if config.DRY_RUN:
        do_skip()
        return
    # Scroll back to the top before tapping a heart. The compose box
    # anchors to the tapped element and extends DOWNWARD — if we tap
    # a heart that's already low on screen (which it is after capture),
    # Send Like ends up off-screen and undetectable. Worth the ~14s.
    scroll_back_to_top()
    heart_xy = vision.find_first_heart(adb.screenshot())
    if heart_xy is None:
        # Static fallback used to fire here, but it silently misses on
        # profiles where the heart's real position differs from the
        # calibrated coord (different layouts, partial scroll-back). The
        # loop would then type/tap into the void and never advance,
        # producing an infinite-loop on the same profile. Bail to skip
        # instead so the profile advances and the loop survives.
        raise RuntimeError("vision: couldn't find photo-1 heart after scroll-back")
    adb.tap(*heart_xy)
    adb.jitter_sleep("after_tap")

    send_xy = vision.find_send_like(adb.screenshot())
    if send_xy is None:
        # Same reasoning as the heart fallback above — silent fallback
        # masks a real failure and traps the loop. Skip instead.
        raise RuntimeError("vision: couldn't find Send Like after heart tap")
    comment_xy = vision.find_comment_input(send_xy)

    if message:
        adb.tap(*comment_xy)
        adb.jitter_sleep("after_tap")
        # Snapshot empty-field text-pixel baseline so we can detect when
        # the typed text has actually landed in the EditText buffer.
        empty_pixels = vision.comment_field_text_pixels(adb.screenshot(), send_xy)
        adb.input_text(message)
        # Poll for the field to fill. Under host CPU contention (e.g. a
        # game running alongside the emulator) `input text` events can
        # dispatch slower than expected — short fixed waits drop chars.
        # Expected pixel count grows with message length (tuned at 1080
        # wide; text area scales with width squared); require we see
        # well above the empty baseline before sending.
        deadline = time.monotonic() + 15
        px_scale = (config.SCREEN_WIDTH / 1080) ** 2
        target_pixels = empty_pixels + int(max(150, 20 * len(message)) * px_scale)
        while time.monotonic() < deadline:
            time.sleep(1.0)
            current = vision.comment_field_text_pixels(adb.screenshot(), send_xy)
            if current >= target_pixels:
                break
        else:
            print(f"WARN: typed text didn't reach expected pixel density "
                  f"(have {current}, want {target_pixels}) — sending anyway.")
        # Typed text can wrap to multiple lines, expanding the comment
        # field and pushing Send Like down. Re-find against the post-type
        # screen so the tap lands on the actual button position.
        post_type_xy = vision.find_send_like(adb.screenshot())
        if post_type_xy is not None:
            send_xy = post_type_xy
    adb.tap(*send_xy)
    adb.jitter_sleep("after_like_sent")


def save_debug(frames: list[bytes], decision, profile_idx: int) -> None:
    if not config.SAVE_DEBUG_FRAMES:
        return
    bucket = "liked" if decision.decision == "like" else "skipped"
    bucket_dir = config.DEBUG_DIR / bucket
    bucket_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-z0-9]", "", (decision.name or "unknown").lower()) or "unknown"
    folder = bucket_dir / f"{profile_idx:02d}_{safe_name}"
    imgs = folder / "imgs"
    imgs.mkdir(parents=True, exist_ok=True)
    for i, png in enumerate(frames):
        (imgs / f"frame_{i:02d}.png").write_bytes(png)
    (folder / "decision.txt").write_text(
        f"name: {decision.name}\n"
        f"decision: {decision.decision}\n"
        f"confidence: {decision.confidence}\n"
        f"reasoning: {decision.reasoning}\n"
        f"message: {decision.message}\n"
        f"message_archetype: {decision.message_archetype}\n"
        f"prompt_referenced: {decision.prompt_referenced}\n"
        f"skip_reason: {decision.skip_reason}\n"
        f"timestamp: {datetime.now().isoformat(timespec='seconds')}\n"
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="HingeAuto loop runner")
    p.add_argument(
        "--mode",
        default=None,
        help="Override config.ACTIVE_MODE for this run (one-shot). "
             "Must match a file under modes/<name>.py.",
    )
    p.add_argument(
        "--max-likes",
        type=int,
        default=None,
        metavar="N",
        help="Override config.MAX_LIKES_PER_SESSION for this run. The loop "
             "stops as soon as the Nth like has been sent. --max-likes 1 "
             "is the live counterpart of --soft-run: same per-profile "
             "reporting, but the like and opener actually go out.",
    )
    p.add_argument(
        "--soft-run",
        action="store_true",
        help="Judge and skip as normal, but stop at the first LIKE decision "
             "without tapping anything. Prints {name, decision, opener} as "
             "JSON and leaves Hinge on that profile for inspection.",
    )
    p.add_argument(
        "--set-filters",
        action="store_true",
        help="Before looping, drive the in-app age slider to match the "
             "active mode's AGE_MIN/AGE_MAX. Requires filter_coords.json "
             "(see calibrate_filters.py).",
    )
    p.add_argument(
        "--location",
        default=None,
        help="Before looping, change Hinge's 'My neighborhood' to the "
             "named city (resolved via locations.json). Orthogonal to "
             "--mode. Requires location_coords.json + Hinge+/X for "
             "out-of-area changes.",
    )
    p.add_argument(
        "--rotate",
        default=None,
        help="Named rotation path from locations.json _rotations (e.g. "
             "'atl'). When Hinge's 'You've seen everyone' screen appears, "
             "advance to the next city in the rotation. Loops back to "
             "start when exhausted.",
    )
    return p.parse_args(argv)


def main() -> int:
    args = _parse_args()
    load_dotenv()

    if args.mode:
        config.ACTIVE_MODE = args.mode
        config._apply_mode()
    if args.max_likes is not None:
        if args.max_likes < 1:
            print("--max-likes must be at least 1.")
            return 2
        config.MAX_LIKES_PER_SESSION = args.max_likes

    serial = adb.check_device()
    print(f"Connected to: {serial}")
    adb.preflight()
    age_band = (
        f"age {config.AGE_MIN}-{config.AGE_MAX}"
        if (config.AGE_MIN is not None or config.AGE_MAX is not None)
        else "no age gate"
    )
    print(f"Mode:     {config.MODE_NAME} ({age_band})")
    run_label = (
        "SOFT RUN (skip until first like, then stop; no like is sent)"
        if args.soft_run else
        "DRY RUN (no taps)" if config.DRY_RUN else "LIVE (will tap)"
    )
    print(f"Run:      {run_label}")
    print(f"Max likes: {config.MAX_LIKES_PER_SESSION}, "
          f"max profiles: {config.MAX_PROFILES_PER_SESSION}")

    if args.set_filters:
        if config.AGE_MIN is None and config.AGE_MAX is None:
            print("--set-filters requested but active mode has no age range; "
                  "skipping in-app filter step.")
        else:
            import filters
            print(f"Setting in-app age filter to {config.AGE_MIN}-{config.AGE_MAX}...")
            filters.set_age_range(config.AGE_MIN, config.AGE_MAX)

    if args.location:
        import locations
        resolved = locations.resolve(args.location)
        print(f"Setting location to '{args.location}' (search: '{resolved}')...")
        locations.set_location(args.location)

    rotation_list: list[str] | None = None
    rotation_idx: int = 0
    if args.rotate:
        import locations
        rotation_list = locations.get_rotation(args.rotate)
        # If --location was also set, start the rotation at that location if
        # it's in the list; otherwise prepend it (don't replace the rotation).
        if args.location and args.location in rotation_list:
            rotation_idx = rotation_list.index(args.location)
        print(f"Rotation '{args.rotate}': {rotation_list} (starting at "
              f"index {rotation_idx} = '{rotation_list[rotation_idx]}')")

    print("Starting in 5s. Make sure Hinge is open on the Discover tab.")
    time.sleep(5)

    likes_sent = 0
    skips = 0
    profiles_seen = 0
    total_cost = 0.0
    total_seconds = 0.0
    last_frame0_hash: str | None = None
    duplicate_streak = 0
    judge_failures_in_a_row = 0

    while profiles_seen < config.MAX_PROFILES_PER_SESSION:
        profiles_seen += 1
        print(f"\n--- Profile {profiles_seen} ---")

        t0 = time.monotonic()
        frames = capture_profile()
        t_capture = time.monotonic() - t0
        # The mode may cap how many frames the judge sees (JUDGE_FRAMES);
        # the full scroll still happens so the phone behaviour looks human.
        judge_frames = frames[:config.JUDGE_FRAMES] if config.JUDGE_FRAMES else frames
        print(f"Captured {len(frames)} frames"
              + (f" (judging first {len(judge_frames)})" if len(judge_frames) < len(frames) else ""))

        # Out-of-candidates detection: if frame 0 shows the "You've seen
        # everyone for now" screen, we're stuck. If --rotate is on, advance
        # to the next city; otherwise just break since further iteration
        # would just force-skip nothing.
        if rotation_list is not None:
            import locations
            if locations.is_out_of_candidates(frames[0]):
                rotation_idx = (rotation_idx + 1) % len(rotation_list)
                next_city = rotation_list[rotation_idx]
                print(f"OUT OF CANDIDATES — rotating to '{next_city}' "
                      f"(index {rotation_idx}/{len(rotation_list) - 1}).")
                try:
                    locations.set_location(next_city)
                except Exception as e:
                    print(f"set_location failed: {e!r} — continuing in place.")
                last_frame0_hash = None
                duplicate_streak = 0
                profiles_seen -= 1  # don't count the empty-state capture
                continue

        # If frame 0 is identical to the previous profile's frame 0, Hinge
        # didn't advance after our last action — force-skip rather than
        # burning another ~$0.035 re-judging the same person. Escalate the
        # delay if we keep duplicating, in case Hinge needs a beat to
        # recover from an "out of likes" / popup state.
        #
        # Hash a cropped region of frame 0 (excluding status bar at top and
        # nav bar at bottom). The status-bar clock ticks every minute and
        # the nav-bar can show transient badges; both make raw-bytes md5
        # diverge across iterations even when the *profile* is identical,
        # which silently breaks duplicate detection. Cropping isolates the
        # part of the screen that actually identifies the profile.
        frame0_hash = _profile_region_hash(frames[0])
        if frame0_hash == last_frame0_hash:
            duplicate_streak += 1
            print(f"DUPLICATE: frame 0 matches previous profile "
                  f"(streak {duplicate_streak}). Force-skipping without judge.")
            try:
                do_skip()
            except Exception as e:
                print(f"Skip failed during duplicate recovery: {e!r}")
            time.sleep(min(2 + duplicate_streak * 2, 15))
            continue
        last_frame0_hash = frame0_hash
        duplicate_streak = 0

        t1 = time.monotonic()
        decision = None
        fatal_error = None
        for attempt in range(3):
            try:
                decision = judge(judge_frames)
                break
            except Exception as e:
                err = repr(e)
                print(f"Judge attempt {attempt + 1}/3 failed: {e}")
                if any(s in err for s in FATAL_JUDGE_ERRORS):
                    fatal_error = err
                    break
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
        if fatal_error is not None:
            print(f"\nFATAL judge error — halting loop instead of burning "
                  f"Hinge swipes:\n  {fatal_error}")
            break
        t_judge = time.monotonic() - t1
        if decision is None:
            judge_failures_in_a_row += 1
            if judge_failures_in_a_row >= MAX_CONSECUTIVE_JUDGE_FAILURES:
                print(f"\nJudge failed on {judge_failures_in_a_row} profiles in a "
                      "row — halting instead of burning Hinge swipes blind.")
                break
            print("Judge failed 3 times — skipping this profile to keep the loop alive.")
            do_skip()
            continue
        judge_failures_in_a_row = 0

        print(f"Name:     {decision.name}")
        print(f"Decision: {decision.decision} ({decision.confidence}) "
              f"[{decision.skip_reason if decision.decision == 'skip' else decision.message_archetype}]")
        print(f"Reason:   {decision.reasoning}")
        if decision.message:
            print(f"Message:  {decision.message}")
        # Live record, same shape for every profile. Nothing is written to
        # disk unless config.SAVE_SESSION_LOG is on.
        print(json.dumps({
            "name": decision.name,
            "decision": decision.decision,
            "opener": decision.message,
        }, indent=2))
        save_debug(frames, decision, profiles_seen)

        t2 = time.monotonic()
        if args.soft_run and decision.decision == "like":
            print("\nSOFT RUN: first LIKE found — stopping here without tapping.")
            break
        if decision.decision == "like":
            if likes_sent >= config.MAX_LIKES_PER_SESSION:
                print(f"Hit max likes cap ({config.MAX_LIKES_PER_SESSION}). Stopping.")
                break
            try:
                do_like(decision.message)
                likes_sent += 1
                print(f"LIKE SENT to {decision.name} with opener {decision.message!r} "
                      f"({likes_sent}/{config.MAX_LIKES_PER_SESSION}).")
                if likes_sent >= config.MAX_LIKES_PER_SESSION:
                    print(f"Reached max likes ({config.MAX_LIKES_PER_SESSION}). Stopping.")
                    metrics.log_profile(profiles_seen, decision, {
                        "capture_seconds": round(t_capture, 2),
                        "judge_seconds": round(t_judge, 2),
                        "act_seconds": round(time.monotonic() - t2, 2),
                        "total_seconds": round(t_capture + t_judge + time.monotonic() - t2, 2),
                    })
                    break
            except Exception as e:
                print(f"do_like failed: {e!r} — recovering by skipping this profile.")
                try:
                    do_skip()
                except Exception as e2:
                    print(f"do_skip recovery also failed: {e2!r} — loop will retry next iter.")
                skips += 1
        else:
            do_skip()
            skips += 1
        t_act = time.monotonic() - t2

        timing = {
            "capture_seconds": round(t_capture, 2),
            "judge_seconds":   round(t_judge, 2),
            "act_seconds":     round(t_act, 2),
            "total_seconds":   round(t_capture + t_judge + t_act, 2),
        }
        metrics.log_profile(profiles_seen, decision, timing)
        total_cost += metrics.estimated_cost(decision.usage)
        total_seconds += timing["total_seconds"]
        metrics.print_running_totals(
            profiles_seen, likes_sent, skips, total_cost, total_seconds,
        )

    print(f"\nDone. {likes_sent} likes sent across {profiles_seen} profiles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
