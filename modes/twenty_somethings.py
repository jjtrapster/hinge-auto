"""Twenty-somethings mode — photo-only, lenient, one rule, one opener.

Age band 21-29 (set it in Hinge's own Age filter; see AGE_MIN below).
The judge looks at the person in photos 1 and 2 and nothing else — no
prompts, no bio, no basic-info text. Default is LIKE and the bar for a
skip is a single rule: clearly overweight, in the strictest sense.
Everything else, including every "can't tell" case, is a like. Every
like sends the same opener.

Leniency is enforced in code, not just asked for: with
SKIP_NEEDS_HIGH_CONFIDENCE a skip only stands when the model rates its
own confidence "high"; any other skip is flipped to a like by
judge_common. Small local models turn uncertainty into skips no matter
how the rubric is worded — this takes that option away.

Why photo-only: with a small local vision model the text-driven rubric
(see git history for the prompt-hijacking version of this mode) produced
confident-sounding skips citing prompt text that wasn't on the profile.
Photos are what a 7B vision model can actually judge, so the rubric was
cut down to that, and the frames sent to the judge are capped
(JUDGE_FRAMES) so the model spends its context on the photos.

Mode-level knobs used here that the examples don't show:
  - JUDGE_FRAMES: main.py still captures all FRAMES_PER_PROFILE frames,
    scrolling the whole profile like a person would, but sends only the
    first N to the judge.
  - FORCE_PREMADE_ID: judge_common overwrites the message on every like
    with this premade, whatever the model wrote.

These are the user's own criteria, written at their request. Edit
PREFERENCES to change them.
"""

NAME = "twenty_somethings"
DESCRIPTION = (
    "Photo-only and lenient: like unless clearly overweight in photos "
    "1-2; skips need high confidence or become likes; fixed opener on "
    "every like. Age band 21-29 via Hinge's in-app filter."
)

# Judge-side age gate OFF: this mode tells the model to ignore all text,
# and the local model misread ages when the gate was on. Set 21-29 in
# Hinge's own Age filter instead. To re-enable the judge gate (and
# --set-filters), put the numbers back.
AGE_MIN = None
AGE_MAX = None

MAX_LIKES_PER_SESSION = None  # inherit config default
MAX_PROFILES_PER_SESSION = None

# All FRAMES_PER_PROFILE frames are captured; only the first 3 go to the
# judge. Photo 1 fills frame 0; photo 2 lands in frame 1 or 2 on the
# layouts seen so far. Raise to 4 if photo 2 keeps getting cut off.
JUDGE_FRAMES = 3

# Every like sends this premade, whatever the model wrote.
FORCE_PREMADE_ID = "can_i_be_honest"

# A skip only stands if the model says confidence == "high". Any other
# skip becomes a like (judge_common.apply_decision_guards). This is the
# "when in doubt, like" rule, enforced.
SKIP_NEEDS_HIGH_CONFIDENCE = True

PREMADES = [
    {
        "id": "can_i_be_honest",
        "message": "Can I be honest?",
        "use_when": "ALWAYS. Every like in this mode sends this line.",
    },
]

MESSAGE_VOICE = """## Message rubric (when decision == "like")

Every like sends the premade can_i_be_honest, verbatim. Never write a
fresh opener. On a like set premade_id to "can_i_be_honest", message to
its text, and message_archetype to "premade". On a skip, message and
premade_id are empty strings."""

PREFERENCES = """
PHOTO-ONLY, LENIENT MODE. Look at the person in the FIRST TWO PHOTOS
and nothing else. Ignore all text on the profile (prompts, bio, job,
school, location). Text is never a reason to like or skip.

Where the photos are: the first screenshot shows photo 1. Photo 2 is in
the next screenshot or the one after. Nothing further down counts.

Default decision: LIKE. Be generous. The vast majority of profiles
should be liked. A missed like costs far more than a bad like.

There is exactly ONE skip rule:
  SKIP only if the person is clearly overweight - obvious at a glance,
  in the strictest sense of the word, in the first two photos.

Everything else is a LIKE. In particular, ALL of these are LIKES:
- blurry photo, dark photo, filtered photo, low quality
- face turned away, partly hidden, sunglasses, hat, mask
- far away, small in the frame, sitting, only the upper body visible
- group photo where you are not sure which person it is
- only one photo visible, or photo 2 cut off
- average-looking, plain, not conventionally pretty - none of that
  matters in this mode
- ANY case where you are not sure. Not sure = LIKE.

Never skip for photo quality or because you cannot see the person
well. If you cannot judge the person's build, the answer is LIKE.

Confidence: "high" ONLY when photos 1 and 2 both show the person's
full build clearly and the decision is obvious. Otherwise "medium" or
"low". A skip that is not "high" confidence is treated as a like.

Reasoning: ONE sentence about the photos. Example: "photo 1 is a clear
full-body shot, photo 2 a close-up; in shape." Never mention ethnicity,
skin colour, age, or anything from the text.

skip_reason: "preferences" on a skip, "none" on a like.
"""
