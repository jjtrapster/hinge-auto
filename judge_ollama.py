"""Ollama backend for HingeAuto judging.

Targets a vision-capable model running on either:
  - Local Ollama  (`ollama serve` on your machine, default
    `http://localhost:11434`)
  - Ollama Cloud  (https://ollama.com — free tier available; set
    `OLLAMA_HOST=https://ollama.com` and `OLLAMA_API_KEY=...`)

The same JSON schema as the Anthropic backend (`judge_common.
DECIDE_INPUT_SCHEMA`) is passed as Ollama's `format=` structured-output
constraint rather than as a tool: most open vision models (`qwen2.5vl`
included) don't support tool calling in Ollama, while constrained JSON
decoding works with every model.

Honest tradeoff vs Anthropic: open vision models are noticeably weaker
at judging a 7-frame profile, and the opener writing is weaker. Cost is
the win — free if you self-host or stay inside Ollama Cloud's free tier.

Set in config.py:
  JUDGE_BACKEND = "ollama"
  OLLAMA_MODEL  = "qwen2.5vl"        # or "llama3.2-vision"
  OLLAMA_HOST   = None                # default localhost; cloud:
                                      # "https://ollama.com"
  OLLAMA_FRAME_SCALE = 0.5            # downscale frames; ~4x faster
  OLLAMA_NUM_CTX = 16384              # 7 full-res frames ~ 15k tokens

Set in your .env (or shell):
  OLLAMA_API_KEY=...   # required for Ollama Cloud, ignored locally
"""

import base64
import copy
import io
import json
import os

from PIL import Image

import config
from judge_common import (
    DECIDE_INPUT_SCHEMA,
    Decision,
    build_system_prompt,
    enforce_premade_verbatim,
)


# Ollama-side copy of the decision schema with hard string-length caps.
# llama.cpp turns maxLength into a grammar bound, so a model that starts
# repeating inside `reasoning` is forced to close the string at the cap
# instead of running until num_predict. Ignored harmlessly by servers
# that don't support it.
_STRING_CAPS = {"name": 40, "reasoning": 400, "message": 200,
                "prompt_referenced": 60, "premade_id": 40}
OLLAMA_SCHEMA = copy.deepcopy(DECIDE_INPUT_SCHEMA)
for _field, _cap in _STRING_CAPS.items():
    OLLAMA_SCHEMA["properties"][_field]["maxLength"] = _cap


def _client():
    try:
        from ollama import Client
    except ImportError as e:
        raise RuntimeError(
            "The `ollama` package isn't installed. Run "
            "`pip install ollama` (or install the optional extras: "
            "`pip install -r requirements-ollama.txt`)."
        ) from e

    host = getattr(config, "OLLAMA_HOST", None) or os.environ.get(
        "OLLAMA_HOST", "http://localhost:11434"
    )
    kwargs = {
        "host": host,
        "timeout": float(getattr(config, "OLLAMA_TIMEOUT", 300)),
    }
    api_key = os.environ.get("OLLAMA_API_KEY")
    if api_key:
        kwargs["headers"] = {"Authorization": f"Bearer {api_key}"}
    return Client(**kwargs)


def _downscale(png: bytes, scale: float) -> bytes:
    if scale >= 1.0:
        return png
    im = Image.open(io.BytesIO(png))
    im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                   Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _images_b64(frames: list[bytes]) -> list[str]:
    scale = float(getattr(config, "OLLAMA_FRAME_SCALE", 1.0))
    return [base64.standard_b64encode(_downscale(f, scale)).decode("utf-8")
            for f in frames]


def _decision_from_args(args: dict, usage: dict) -> Decision:
    """Build Decision from a tool-call argument dict, tolerating mild
    schema drift (open models miss keys more often than Claude)."""
    defaults = {
        "name": "unknown",
        "decision": "skip",
        "confidence": "low",
        "reasoning": "",
        "message": "",
        "skip_reason": "other",
        "message_archetype": "empty",
        "premade_id": "",
        "prompt_referenced": "",
    }
    merged = {**defaults, **{k: v for k, v in args.items() if k in defaults}}
    # Clamp enum-like fields to allowed values
    if merged["decision"] not in ("like", "skip"):
        merged["decision"] = "skip"
    if merged["confidence"] not in ("low", "medium", "high"):
        merged["confidence"] = "low"
    return Decision(**merged, usage=usage)


def judge(frames: list[bytes]) -> Decision:
    """Given an ordered list of PNG frames of one profile, return a Decision."""
    client = _client()
    model = getattr(config, "OLLAMA_MODEL", "qwen2.5vl")

    user_text = (
        f"Above are {len(frames)} screenshots of one Hinge profile, in order "
        "from top to bottom. Decide whether to like or skip, and respond "
        "with the submit_decision JSON object."
    )

    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": build_system_prompt()},
            {
                "role": "user",
                "content": user_text,
                "images": _images_b64(frames),
            },
        ],
        format=OLLAMA_SCHEMA,
        options={
            "temperature": 0.2,
            "num_ctx": getattr(config, "OLLAMA_NUM_CTX", 16384),
            # Brakes. Small models loop inside string fields under
            # constrained decoding; the penalty discourages the loop and
            # num_predict guarantees it ends. See OLLAMA_NUM_PREDICT.
            "repeat_penalty": 1.15,
            "repeat_last_n": 256,
            "num_predict": int(getattr(config, "OLLAMA_NUM_PREDICT", 400)),
        },
    )

    usage = {
        "input_tokens": getattr(response, "prompt_eval_count", 0) or 0,
        "output_tokens": getattr(response, "eval_count", 0) or 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }

    done_reason = (
        response.get("done_reason") if isinstance(response, dict)
        else getattr(response, "done_reason", None)
    )
    message = response.get("message") if isinstance(response, dict) else response.message
    content = (
        message.get("content") if isinstance(message, dict)
        else getattr(message, "content", "")
    ) or ""
    # Constrained decoding should yield bare JSON, but tolerate fences or
    # leading prose from models that ignore the constraint.
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            decision = _decision_from_args(data, usage)
            enforce_premade_verbatim(decision)
            return decision

    if done_reason == "length":
        raise RuntimeError(
            f"Ollama ({model}) hit the OLLAMA_NUM_PREDICT cap "
            f"({usage['output_tokens']} tokens) without closing the JSON — "
            f"the model looped. Tail: {content[-160:]!r}"
        )
    raise RuntimeError(
        f"Ollama ({model}) did not return a usable submit_decision JSON "
        f"object (done_reason={done_reason!r}, got: {content[:200]!r}). "
        f"Try a different OLLAMA_MODEL (e.g. 'qwen2.5vl:32b' or "
        f"'llama3.2-vision:11b') or check that the model is pulled."
    )
