#!/usr/bin/env python3
"""Apply the wrapper's environment overrides to a Strata model config.

Called by the container entry point after setup and before the server starts:

    PREFILL                 --prefill value (auto, auto:32768, 2048, ...)
    CONVERSATION_CACHE_MIB  --conversation-cache-mib value (MiB, positive int)
    FIT_MAX_TOKENS          top-level "fit_max_tokens" (true/false/yes/no/1/0)
    SAMPLING_TEMPERATURE    "sampling".temperature (number >= 0)
    SAMPLING_TOP_P          "sampling".top_p (0 < value <= 1)
    SAMPLING_TOP_K          "sampling".top_k (integer 1..64)
    SAMPLING_MIN_P          "sampling".min_p (0 <= value <= 1)
    SAMPLING_PRESENCE_PENALTY   "sampling".presence_penalty (number >= 0)
    SAMPLING_REPETITION_PENALTY "sampling".repetition_penalty (number > 0)
    SAMPLING_FREQUENCY_PENALTY  "sampling".frequency_penalty (number >= 0)
    SAMPLING_PENALTY_LAST_N     "sampling".penalty_last_n (integer >= 0)
    SAMPLING_SEED               "sampling".seed (integer > 0)

Unset variables leave the config untouched. Values are written into the model
config, so they persist on later starts without the variables; the helper is a
no-op when nothing would change.
"""
import json
import math
import os
import re
import sys

# (env var, sampling key, cast, valid, expected message)
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
BOOLS = ("1", "0", "true", "false", "yes", "no", "on", "off")


def set_arg(args, flag, value):
    """Replace every occurrence of `flag` (and its value) with one at the end; True if args changed."""
    before = list(args)
    while flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            del args[i:i + 2]
        else:
            del args[i]
    args.extend([flag, value])
    return args != before


def parse_sampling(env):
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


def main():
    if len(sys.argv) != 2:
        print("usage: strata-env-config.py <config.json>", file=sys.stderr)
        return 2

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    changed = False

    args = cfg.setdefault("args", [])
    prefill = os.environ.get("PREFILL", "").strip()
    if prefill:
        if not re.fullmatch(r"auto(?::[0-9]+)?|[0-9]+", prefill):
            print(f"PREFILL must be auto, auto:<tokens> or a token count (got {prefill!r})", file=sys.stderr)
            return 1
        changed |= set_arg(args, "--prefill", prefill)

    cache = os.environ.get("CONVERSATION_CACHE_MIB", "").strip()
    if cache:
        if not cache.isdigit() or int(cache) <= 0:
            print(f"CONVERSATION_CACHE_MIB must be a positive integer (got {cache!r})", file=sys.stderr)
            return 1
        changed |= set_arg(args, "--conversation-cache-mib", cache)

    fit = os.environ.get("FIT_MAX_TOKENS", "").strip().lower()
    if fit:
        if fit not in BOOLS:
            print(f"FIT_MAX_TOKENS must be true or false (got {fit!r})", file=sys.stderr)
            return 1
        value = fit in ("1", "true", "yes", "on")
        if cfg.get("fit_max_tokens") != value:
            cfg["fit_max_tokens"] = value
            changed = True

    sampling_values = parse_sampling(os.environ)
    if sampling_values:
        sampling = cfg.get("sampling")
        if sampling is None:
            sampling = {}
        elif not isinstance(sampling, dict):
            print("config sampling is not an object; cannot apply SAMPLING_* overrides", file=sys.stderr)
            return 1
        for key, value in sampling_values.items():
            if sampling.get(key) != value:
                sampling[key] = value
                changed = True
            if key in ALIASES and ALIASES[key] in sampling:
                del sampling[ALIASES[key]]
                changed = True
        cfg["sampling"] = sampling

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=1)
        applied = []
        if prefill:
            applied.append(f"prefill={prefill}")
        if cache:
            applied.append(f"conversation_cache_mib={cache}")
        if fit:
            applied.append(f"fit_max_tokens={cfg.get('fit_max_tokens')}")
        applied += [f"sampling.{k}={v}" for k, v in sampling_values.items()]
        print("wrapper config: " + ", ".join(applied))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
