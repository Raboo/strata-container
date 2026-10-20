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


def patch_dockerfile(root: Path) -> None:
    """The Terminal stage runs `git rev-parse` (package_terminal.py writes COMMIT); the base lacks git."""
    path = root / "docker" / "Dockerfile"
    text = path.read_text(encoding="utf-8")
    old = "apt-get install -y --no-install-recommends python3 ca-certificates"
    if "python3 ca-certificates git" in text:
        return
    if old not in text:
        raise SystemExit(f"{path}: the Terminal stage's apt line changed; update docker/patch-terminal.py")
    path.write_text(text.replace(old, old + " git", 1), encoding="utf-8")
    print(f"{path}: added git to the Terminal build stage")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    path = root / "strata_cli" / "launch" / "runner.py"
    text = path.read_text(encoding="utf-8")
    if "wrapper_env.apply(base, path=base_path)" in text:
        print(f"{path}: already patched")
        patch_dockerfile(root)
        return 0
    if text.count(ANCHOR) != 1:
        raise SystemExit(f"{path}: expected one 'base = read_config(base_path)' line; update docker/patch-terminal.py")
    text = text.replace(ANCHOR, ANCHOR + CALL, 1)
    path.write_text(text, encoding="utf-8")
    print(f"{path}: patched build_config")
    patch_dockerfile(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
