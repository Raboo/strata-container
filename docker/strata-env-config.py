#!/usr/bin/env python3
"""Apply the wrapper's environment overrides to a Strata model config.

Called by the container entry point after setup and before the server starts:

    PREFILL                 --prefill value (auto, auto:32768, 2048, ...)
    CONVERSATION_CACHE_MIB  --conversation-cache-mib value (MiB, positive int)
    FIT_MAX_TOKENS          top-level "fit_max_tokens" (true/false/yes/no/1/0)

Unset variables leave the config untouched. Values are written into the model
config, so they persist on later starts without the variables.
"""
import json
import os
import re
import sys


def set_arg(args, flag, value):
    while flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            del args[i:i + 2]
        else:
            del args[i]
    args.extend([flag, value])


def main():
    if len(sys.argv) != 2:
        print("usage: strata-env-config.py <config.json>", file=sys.stderr)
        return 2

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    args = cfg.setdefault("args", [])

    prefill = os.environ.get("PREFILL", "").strip()
    if prefill:
        if not re.fullmatch(r"auto(?::[0-9]+)?|[0-9]+", prefill):
            print(f"PREFILL must be auto, auto:<tokens> or a token count (got {prefill!r})", file=sys.stderr)
            return 1
        set_arg(args, "--prefill", prefill)

    cache = os.environ.get("CONVERSATION_CACHE_MIB", "").strip()
    if cache:
        if not cache.isdigit() or int(cache) <= 0:
            print(f"CONVERSATION_CACHE_MIB must be a positive integer (got {cache!r})", file=sys.stderr)
            return 1
        set_arg(args, "--conversation-cache-mib", cache)

    fit = os.environ.get("FIT_MAX_TOKENS", "").strip().lower()
    if fit:
        if fit not in ("1", "0", "true", "false", "yes", "no", "on", "off"):
            print(f"FIT_MAX_TOKENS must be true or false (got {fit!r})", file=sys.stderr)
            return 1
        cfg["fit_max_tokens"] = fit in ("1", "true", "yes", "on")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=1)
    print(f"wrapper config: prefill={prefill or '-'} conversation_cache_mib={cache or '-'} "
          f"fit_max_tokens={cfg.get('fit_max_tokens', '-')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
