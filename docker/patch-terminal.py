#!/usr/bin/env python3
"""Patch Strata's Terminal so the wrapper's environment overrides are applied.

Usage: docker/patch-terminal.py <checkout>

Adds the `wrapper_env.apply(base, path=base_path)` call to
`strata_cli/launch/runner.py:build_config`: the installed run config is read,
the wrapper variables are applied (and persisted), then the launch derives its
private copy from it. An upstream change fails the build loudly.
"""
import sys
from pathlib import Path

ANCHOR = "        base = read_config(base_path)\n"
CALL = (
    "        from strata_cli.launch import wrapper_env\n"
    "        base = wrapper_env.apply(base, path=base_path)\n"
)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    path = root / "strata_cli" / "launch" / "runner.py"
    text = path.read_text(encoding="utf-8")
    if "wrapper_env.apply(base, path=base_path)" in text:
        print(f"{path}: already patched")
        return 0
    if text.count(ANCHOR) != 1:
        raise SystemExit(f"{path}: expected one 'base = read_config(base_path)' line; update docker/patch-terminal.py")
    text = text.replace(ANCHOR, ANCHOR + CALL, 1)
    path.write_text(text, encoding="utf-8")
    print(f"{path}: patched build_config")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
