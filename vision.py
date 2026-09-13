"""Image-based detection for UI elements whose position varies per profile.

Tapping a heart turns that photo/prompt card into an inline compose card
(comment field + Rose + Send Like), so the compose elements sit wherever
the tapped card was. Static COORDS in config don't survive across
profiles — we find these elements at tap-time.

Pixel thresholds were measured on a 720x1600 screen and are scaled by
SCREEN_WIDTH / 720; Hinge lays out in dp so sizes track screen width.
"""

import io
from collections.abc import Iterator

import numpy as np
from PIL import Image
from scipy.ndimage import label, find_objects

import config

_REF_WIDTH = 720


def _scale() -> float:
    return config.SCREEN_WIDTH / _REF_WIDTH


def _png_to_array(png: bytes) -> np.ndarray:
    return np.array(Image.open(io.BytesIO(png)).convert("RGB"))


def _blobs(mask: np.ndarray) -> Iterator[tuple[int, int, int, int, int]]:
    """Yield (cx, cy, w, h, area) for each connected component in `mask`."""
    labeled, _ = label(mask)
    for i, sl in enumerate(find_objects(labeled), 1):
        if sl is None:
            continue
        y0, y1 = sl[0].start, sl[0].stop
        x0, x1 = sl[1].start, sl[1].stop
        area = int((labeled[sl] == i).sum())
        yield (x0 + x1) // 2, (y0 + y1) // 2, x1 - x0, y1 - y0, area


def find_send_like(png: bytes) -> tuple[int, int] | None:
    """Locate the 'Send Like' pill on the inline compose card.

    Light peach pill (~238,225,219), ~373x78 px at 720 wide, right half
    of the screen next to the purple Rose button. Filters on colour, pill
    size, solid fill and x position; when several pass, the topmost wins
    (the compose card sits above anything else on screen that matches).
    """
    s = _scale()
    arr = _png_to_array(png)
    r, g, b = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
    peach = (
        (r > 225) & (g > 205) & (g < 242) & (b > 195) & (b < 235)
        & (r > g) & (g > b) & ((r - b) > 10)
    )
    width = arr.shape[1]
    candidates = []
    for cx, cy, w, h, area in _blobs(peach):
        if not (300 * s < w < 450 * s and 55 * s < h < 100 * s):
            continue
        if area < 0.8 * w * h:
            continue
        if cx < width * 0.5:
            continue
        candidates.append((cy, cx))
    if not candidates:
        return None
    candidates.sort()
    cy, cx = candidates[0]
    return (cx, cy)


def find_first_heart(png: bytes) -> tuple[int, int] | None:
    """Locate the topmost heart button in the current view.

    Hinge's heart is a near-black circle (~91 px at 720 wide) with a white
    heart outline cut out of it, at the bottom-right of every photo and
    prompt card. Profile layouts vary — some open with a prompt card —
    so we return the topmost match, which is card 1 when scrolled to top.

    The white cut-out makes the circle fill ~0.68 of its bounding box;
    a solid dark disc in a photo fills ~0.785, so the fill window rejects
    those. Right-alignment (cx > 70% of width) rejects the rest.
    """
    s = _scale()
    arr = _png_to_array(png)
    dark = arr.max(axis=2) < 40
    width = arr.shape[1]
    hearts = []
    for cx, cy, w, h, area in _blobs(dark):
        if not (80 * s < w < 105 * s and 80 * s < h < 105 * s):
            continue
        if abs(w - h) >= 8 * s:
            continue
        fill = area / (w * h)
        if not (0.55 < fill < 0.75):
            continue
        if cx < width * 0.7:
            continue
        hearts.append((cy, cx))
    if not hearts:
        return None
    hearts.sort()
    cy, cx = hearts[0]
    return (cx, cy)


def comment_field_text_pixels(png: bytes, send_like_xy: tuple[int, int]) -> int:
    """Count dark (text) pixels in the comment field above Send Like.

    Empty field shows only faint grey placeholder ('Add a comment') — very
    few dark pixels. A filled field has many dark pixels from typed text.
    Used to verify that `adb shell input text` actually landed before
    Send Like fires (events can drop under host CPU contention).
    """
    s = _scale()
    arr = _png_to_array(png)
    width = arr.shape[1]
    _, sy = send_like_xy
    y0 = max(0, int(sy - 180 * s))
    y1 = max(0, int(sy - 55 * s))
    x0 = int(width * 0.08)
    x1 = int(width * 0.92)
    region = arr[y0:y1, x0:x1]
    if region.size == 0:
        return 0
    dark = (region.max(axis=-1) < 130).sum()
    return int(dark)


def find_comment_input(send_like_xy: tuple[int, int]) -> tuple[int, int]:
    """Comment field sits at a fixed offset above Send Like, spanning the
    card's full width. Measured 116 px above at 720 wide; stable because
    the compose card's internal layout is fixed — only the card moves.
    """
    _, send_y = send_like_xy
    return (config.SCREEN_WIDTH // 2, int(send_y - 116 * _scale()))
