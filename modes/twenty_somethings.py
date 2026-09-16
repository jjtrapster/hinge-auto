"""Twenty-somethings mode — photo-only, first two photos, one fixed opener.

Age band 21-29 (set it in Hinge's own Age filter; see AGE_MIN below).
The judge looks at the person in photos 1 and 2 and nothing else — no
prompts, no bio, no basic-info text. Default is LIKE; it skips only on
the user's two stated criteria. Every like sends the same opener.

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
    "Photo-only: judge the person in photos 1-2, default LIKE, fixed "
    "opener on every like. Age band 21-29 via Hinge's in-app filter."
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
PHOTO-ONLY MODE. Judge the person in the FIRST TWO PHOTOS and nothing
else.

Ignore every piece of text on the profile: prompts, prompt answers,
bio, job, school, location, dating intentions. Do not read it. Do not
mention it in your reasoning. Text is never a reason to like or skip.

Where the photos are: the first screenshot shows photo 1. Photo 2 is in
the next screenshot or the one after. Judge only those two photos.
Anything further down is not part of the decision.

Default decision: LIKE.

SKIP only if, from photos 1 and 2, one of these is CLEARLY true:
1. The person appears overweight.
2. The person's face is clearly unattractive by common standards.

If you cannot tell - face turned away, sunglasses, far away, a group
photo where the person isn't obvious, only one photo visible - LIKE.
Unclear is not a skip.

Confidence: "high" when both photos show the person's face and build
clearly; "medium" when one does; "low" otherwise.

Reasoning: ONE sentence, about the photos only. Example: "photo 1 is a
clear face shot, photo 2 is full-body on a hike, in shape." Never
mention ethnicity, skin colour, age, or anything from the text.

skip_reason: "preferences" on a skip, "none" on a like.
"""
