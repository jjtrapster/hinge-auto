"""Mode bundles for HingeAuto.

Each mode is a Python module under `modes/` exporting at minimum `NAME` and
`PREFERENCES`. Optional: `AGE_MIN`, `AGE_MAX`, `MESSAGE_VOICE`, `PREMADES`,
`MAX_LIKES_PER_SESSION`, `MAX_PROFILES_PER_SESSION`, `JUDGE_FRAMES` (send
only the first N captured frames to the judge), `FORCE_PREMADE_ID` (every
like sends this premade regardless of what the model wrote),
`SKIP_NEEDS_HIGH_CONFIDENCE` (a skip below "high" confidence becomes a like).

`config.py` resolves the active mode at import time via `config._apply_mode()`
and writes the mode's constants into `config`'s module globals, so callers
keep using `config.PREFERENCES` etc. unchanged.
"""

import importlib
from types import ModuleType


def load(name: str) -> ModuleType:
    try:
        return importlib.import_module(f"modes.{name}")
    except ModuleNotFoundError as e:
        raise KeyError(
            f"Unknown mode {name!r}. Create modes/{name}.py to define it."
        ) from e
