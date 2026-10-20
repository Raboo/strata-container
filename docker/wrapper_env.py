"""Wrapper-only environment overrides for a Strata launch run config.

Injected next to ``strata_cli/launch/runner.py`` at image build time and called
from ``build_config`` on the installed run config, before each launch derives
its private copy. Values are written to the installed config, so they persist
on later starts; unset variables leave it untouched.

    PREFILL                 --prefill (engine option, user_args)
    CONVERSATION_CACHE_MIB  --conversation-cache-mib (engine option, user_args)
    SAMPLING_*              the "sampling" block
    DRAFT_VOCAB             the draft layer's token subset (cjk|en|cyrillic|fr);
                            also copies the subset into the MTP folder
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import sys
from pathlib import Path

SAMPLING = (
    ("SAMPLING_TEMPERATURE", "temperature", float, lambda v: v >= 0, "a number >= 0"),
    ("SAMPLING_TOP_P", "top_p", float, lambda v: 0 < v <= 1, "a number 0 < value <= 1"),
    ("SAMPLING_TOP_K", "top_k", int, lambda v: 1 <= v <= 64, "an integer 1..64"),
    ("SAMPLING_MIN_P", "min_p", float, lambda v: 0 <= v <= 1, "a number 0 <= value <= 1"),
    ("SAMPLING_PRESENCE_PENALTY", "presence_penalty", float, lambda v: v >= 0, "a number >= 0"),
    ("SAMPLING_REPETITION_PENALTY", "repetition_penalty", float, lambda v: v > 0, "a number > 0 (1 = off)"),
    ("SAMPLING_FREQUENCY_PENALTY", "frequency_penalty", float, lambda v: v >= 0, "a number >= 0"),
    ("SAMPLING_PENALTY_LAST_N", "penalty_last_n", int, lambda v: v >= 0, "a non-negative integer"),
    ("SAMPLING_SEED", "seed", int, lambda v: v > 0, "a positive integer"),
)
# llama.cpp's names for the same two settings; keeping both makes the server refuse to start
ALIASES = {"repetition_penalty": "repeat_penalty", "penalty_last_n": "repeat_last_n"}
DRAFT_VOCABS = {"cjk": "draft_vocab.bin", "en": "draft_vocab_en.bin",
                "cyrillic": "draft_vocab_cyrillic.bin", "fr": "draft_vocab_fr.bin"}


def _set_user_arg(cfg: dict, flag: str, value: str) -> None:
    """Set an engine option in the config's user_args (the options setup keeps over its own)."""
    current = cfg.get("user_args")
    try:
        from strata_control import user_args as ua
        cfg["user_args"] = ua.set_flag(list(current or []), flag, value)
        return
    except Exception:                                      # noqa: BLE001 - the module is always there in a real Terminal
        pass
    args = [str(x) for x in (current or [])]
    while flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            del args[i:i + 2]
        else:
            del args[i]
    args.extend([flag, value])
    cfg["user_args"] = args


def _parse_sampling(env) -> dict:
    out = {}
    for var, key, cast, valid, expect in SAMPLING:
        raw = env.get(var, "").strip()
        if not raw:
            continue
        try:
            value = cast(raw)
        except ValueError:
            raise SystemExit(f"{var}={raw!r}: expected {expect}") from None
        if isinstance(value, float) and not math.isfinite(value):
            raise SystemExit(f"{var}={raw!r}: expected {expect}")
        if not valid(value):
            raise SystemExit(f"{var}={raw!r}: expected {expect}")
        out[key] = value
    return out


def _mtp_dir(cfg: dict) -> Path | None:
    args = [str(a) for a in cfg.get("args") or []]
    if "--mtp" not in args[:-1]:
        return None
    value = args[args.index("--mtp") + 1]
    return Path(value) if value else None


def _install_draft_vocab(cfg: dict, choice: str) -> None:
    if cfg.get("mtp") is False:                            # the launch runs without the draft layer
        return
    mtp = _mtp_dir(cfg)
    if mtp is None or not mtp.is_dir():
        return
    root = Path(__file__).resolve().parents[2]             # /opt/strata/terminal (or the checkout)
    src = root / "data" / DRAFT_VOCABS[choice]
    if not src.is_file():
        print(f"wrapper: draft vocabulary {choice!r} is not in {src}; leaving the installed one", file=sys.stderr)
        return
    try:
        shutil.copyfile(src, mtp / "draft_vocab.bin")
    except OSError as exc:
        print(f"wrapper: could not install the {choice!r} draft vocabulary: {exc}", file=sys.stderr)


def apply(cfg: dict, path: Path | None = None) -> dict:
    """Apply the environment to an installed run config; write it back when `path` is given."""
    env = os.environ
    original = json.dumps(cfg, sort_keys=True)

    prefill = env.get("PREFILL", "").strip()
    if prefill:
        if not re.fullmatch(r"auto(?::[0-9]+)?|[0-9]+", prefill):
            raise SystemExit(f"PREFILL must be auto, auto:<tokens> or a token count (got {prefill!r})")
        _set_user_arg(cfg, "--prefill", prefill)

    cache = env.get("CONVERSATION_CACHE_MIB", "").strip()
    if cache:
        if not cache.isdigit() or int(cache) <= 0:
            raise SystemExit(f"CONVERSATION_CACHE_MIB must be a positive integer (got {cache!r})")
        _set_user_arg(cfg, "--conversation-cache-mib", cache)

    values = _parse_sampling(env)
    if values:
        sampling = cfg.get("sampling")
        if sampling is None:
            sampling = {}
        elif not isinstance(sampling, dict):
            raise SystemExit("the run config's sampling block is not an object; cannot apply SAMPLING_* overrides")
        for key, value in values.items():
            sampling[key] = value
            if key in ALIASES:
                sampling.pop(ALIASES[key], None)
        cfg["sampling"] = sampling

    vocab = env.get("DRAFT_VOCAB", "").strip().lower()
    if vocab:
        if vocab not in DRAFT_VOCABS:
            raise SystemExit(f"DRAFT_VOCAB must be one of {', '.join(DRAFT_VOCABS)} (got {vocab!r})")
        cfg["draft_vocab"] = vocab
        _install_draft_vocab(cfg, vocab)

    if path is not None and json.dumps(cfg, sort_keys=True) != original:
        target = Path(path)
        tmp = target.with_name(target.name + ".wrapper.tmp")
        tmp.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
        os.replace(tmp, target)
    return cfg
