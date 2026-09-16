"""Twenty-somethings mode — peer age band, prompt-hijacking openers.

A themed mode for a user in their twenties liking other twenty-somethings
(21-29). Where `cougar.py` gets its hook from an age gap, this mode gets
it from the prompts themselves: every opener treats the profile's prompt
as a game they started and plays along — calls the lie, accepts the bet,
takes the other side of the debate, RSVPs to the plan.

Why prompts, not photos: Hinge's own numbers say a comment on a prompt
out-converts a comment on a photo by about half again, a comment beats a
bare like roughly 2x, and an observation paired with a question beats
either alone. "Two truths and a lie" is the single best-converting
prompt to open on. The PREMADES below are keyed to the interactive
prompt titles the 20s crowd actually uses, so the judge (which may be a
small local vision model) has a reliable, on-brand line for most
profiles without having to write anything.

Demonstrates:
  - AGE_MIN / AGE_MAX (judge-side gate; pair with --set-filters to also
    drive Hinge's in-app slider)
  - Inline MESSAGE_VOICE
  - Prompt-title-triggered PREMADES with one universal fallback

What this mode is NOT: a demographic-filter mode. PREFERENCES is about
whether there's something on the profile to open on, not about who
deserves a like. Add taste rules in your own private copy if you want
them.
"""

NAME = "twenty_somethings"
DESCRIPTION = (
    "Peer age band (21-29) with prompt-hijacking openers: calls the lie, "
    "accepts the bet, takes the other side. Pair with "
    "`python main.py --mode twenty_somethings --set-filters` to also "
    "drive Hinge's in-app age slider."
)

# Judge-side backstop for the in-app filter. Hinge shows age next to
# height/location in the basic-info row.
AGE_MIN = 21
AGE_MAX = 29

MAX_LIKES_PER_SESSION = None  # inherit config default
MAX_PROFILES_PER_SESSION = None

# Verbatim openers, each keyed to prompt TITLES that appear on-screen as
# the small heading above a prompt answer. The judge matches the title
# it can read, not the vibe. Messages are 10-25 words, lowercase, plain
# ASCII, and each ends on something answerable in one sentence.
PREMADES = [
    {
        "id": "ttl_call_the_lie",
        "message": "calling it now, the second one is the lie. if i'm wrong you owe me a better lie",
        "use_when": (
            "A prompt titled 'Two truths and a lie' is visible with three "
            "readable text lines (not a voice prompt). This is the best "
            "prompt on Hinge to open on, so prefer it over every other "
            "premade. If you can confidently tell which line is the lie, "
            "write a fresh opener that names it instead."
        ),
    },
    {
        "id": "debate_other_side",
        "message": "taking the other side of this one purely on principle. make your case",
        "use_when": (
            "A prompt titled 'Let's debate about', 'Change my mind about', "
            "'Do you agree or disagree that', 'My most controversial "
            "opinion is' or 'I'm convinced that' is visible AND the topic "
            "is low-stakes (food, music, movies, habits, sports). Never on "
            "politics, religion, bodies or anything personal."
        ),
    },
    {
        "id": "win_me_over_short_list",
        "message": "if that's the whole list this is going to be a short recruitment process. what did you leave off",
        "use_when": (
            "A prompt titled 'The way to win me over is', 'The key to my "
            "heart is', 'I'll fall for you if', 'All I ask is that you', "
            "'We'll get along if' or 'First round is on me if' is visible "
            "and the answer is a short, easy-sounding list or condition."
        ),
    },
    {
        "id": "bet_accepted",
        "message": "bet accepted. i'll need terms though, what do i get when i win",
        "use_when": (
            "A prompt titled 'I bet you can't', 'Try to guess this about "
            "me', 'Never have I ever' or 'Unusual skills' is visible."
        ),
    },
    {
        "id": "suspiciously_well_rested",
        "message": "this sounds suspiciously well rested, what does the real version look like",
        "use_when": (
            "A prompt titled 'Typical Sunday', 'My simple pleasures', 'I "
            "wind down by', 'To me, relaxation is' or 'After work you can "
            "find me' is visible and the answer is wholesome or cosy "
            "(coffee, walks, naps, reading, farmers market)."
        ),
    },
    {
        "id": "valid_defend_in_court",
        "message": "ok that one is actually valid and i'll defend it in court. what's the origin story",
        "use_when": (
            "A prompt titled 'My most irrational fear', 'The dorkiest thing "
            "about me is', 'Don't hate me if I', 'I'm weirdly attracted to' "
            "or 'A shower thought I recently had' is visible with a "
            "specific, slightly odd answer."
        ),
    },
    {
        "id": "rsvp_yes",
        "message": "in. when are we doing this and what do i need to bring",
        "use_when": (
            "A prompt titled 'Together, we could', 'This year, I really "
            "want to', 'On my bucket list', 'A life goal of mine' or 'The "
            "best way to ask me out is by' is visible and the answer "
            "describes an activity, trip or plan."
        ),
    },
    {
        "id": "one_controversial_tip",
        "message": "i have exactly one tip for that and it is controversial, want it",
        "use_when": (
            "A prompt titled 'Give me travel tips for', 'Teach me something "
            "about' or 'One thing I'd love to know about you is' is visible."
        ),
    },
    {
        "id": "prompt_ranking",
        "message": "which of your three prompts do you think is the strongest, i have a ranking and want to compare",
        "use_when": (
            "LAST RESORT. The profile has readable text prompts but none of "
            "the titles above match and no answer is specific enough to "
            "write a fresh opener about. Works on any profile with text "
            "prompts. Never use it when a better premade or a fresh opener "
            "is available."
        ),
    },
]

# Inline voice — overrides judge_common.DEFAULT_MESSAGE_VOICE for this
# mode. Could equivalently live in voice/prompt_hijack.py.
MESSAGE_VOICE = """## Message rubric (when decision == "like")

Most likes should go out with a PREMADE keyed to a prompt title on the
profile - that is the point of this mode. Write a fresh opener only
when a prompt ANSWER is specific enough that a line about that exact
answer beats the premade.

Comment on prompts, not photos. Fall back to a photo detail only when
there is no readable text prompt at all.

When writing fresh:

**Voice:**
- All lowercase. No exclamation marks.
- 10-25 words (roughly 50-120 characters).
- Play along with the prompt as if they started a game: call the lie,
  accept the bet, take the other side, RSVP to the plan, ask for the
  real version, answer the question they asked.
- One specific reference plus a light tease or a question they can
  answer in one sentence. Both together is best.
- Sound like a 25-year-old texting someone they have already decided
  is funny. Confident, a bit dry, never earnest, never thirsty.

**Avoid:**
- Opening with hey, hi, hello, or their name.
- Compliments on looks, or on the profile in general.
- "genuinely", "honestly", "literally", "obsessed", "love that",
  "iconic", "fellow [x]", "the way you", "big fan of".
- Pickup lines, wordplay on their name, anything from a listicle.
- Questions the profile already answers, or boring ones (where do
  you work, how long have you lived here).
- Anything sexual. Anything about their body.
- Em-dashes. Plain hyphens and periods only.

**Examples of the shape (do not copy; write your own for the profile):**
- prompt: I go crazy for / a good farmers market
  opener: farmers market is a strong claim, what is the best thing you
  have actually bought at one
- prompt: Green flags I look for / someone who can cook one thing well
  opener: i can cook exactly one thing well and i am not saying what
  it is yet
- prompt: My go-to karaoke song is / Mr Brightside
  opener: mr brightside is the safe pick and you know it, what is the
  risky one

**Hard constraints:**
- Plain ASCII only. No emoji, no smart quotes, no em-dashes.
- Avoid the characters \\, ", $, ` - they break the typing layer.
- Empty string when decision == "skip".
- If you would like the profile but cannot write anything specific and
  no other premade fits, use the prompt_ranking premade rather than
  sending an empty message."""

PREFERENCES = """
This mode is for liking other twenty-somethings (21-29) with openers
that play along with their prompts. It is NOT a demographic-filter
mode. Decisions are about whether there is something on the profile
to open on, not about who deserves a like.

Default: LIKE. Lean strongly toward LIKE. The age gate and Hinge's own
filters already narrow the pool; the openers do the rest of the
filtering at the reply stage.

SKIP signals (use sparingly):

1. Bot / spam / promo. Concrete signals: a single AI-looking or stock
   photo; the bio or a prompt is mainly an off-platform handle or a
   link (snap, insta, telegram, onlyfans, "dm me on"); photos
   contradict the stated info; the profile reads as an advert.
   Use skip_reason="low_effort".

2. Explicitly not here to date. The profile SAYS it in text: "just
   here for friends", "not looking for anything right now", "here to
   promote", "on here for my friend". A vague or joking prompt does
   not count. Use skip_reason="other".

3. Nothing to open on at all: no readable text prompts (only voice
   prompts or polls) AND no specific photo detail (an activity, a
   place, an object) to reference. Basic info alone (job, school,
   height) is not enough. With the prompt_ranking premade available
   this should almost never fire. Use skip_reason="low_effort".

Everything else is a LIKE. Career, school, hobbies, drinking, pets,
distance, photo quality, group photos, how many prompts are filled
in, whether their taste matches the user's - none of these are skip
signals. Don't get clever.

Picking the opener:
- Read every prompt TITLE on the profile (the small heading above
  each answer). If one matches a premade's use_when, use that premade
  and put the prompt title in prompt_referenced.
- If a prompt ANSWER is specific and you can write a line about that
  exact answer, write fresh per the voice rules. Specific beats
  premade.
- Otherwise prompt_ranking.

When writing reasoning:
- Name the prompt or photo you are reacting to ("the Two truths and a
  lie prompt", "photo 3 at the climbing gym").
- Stay neutral and non-judgmental about the person. The rubric is
  about having something to say, not a verdict on them.
"""
