#!/usr/bin/env python3
"""Patch an upstream Strata checkout for the container images.

Usage: docker/patch-upstream.py <checkout> [--portable]

  --portable   add -DSTRATA_PORTABLE=ON to the CUDA and vision builds (x86_64
               only: it selects an AVX2 CPU baseline). Skip it on arm64, where
               the upstream native build is correct.

Always patches docker-entrypoint.sh:
  * DRAFT_VOCAB -> --draft-vocab (setup and start)
  * PREFILL / CONVERSATION_CACHE_MIB / FIT_MAX_TOKENS / SAMPLING_* through
    strata-env-config.py, before the server starts
  * the AVX2 warning is x86-only (an arm64 host otherwise warns on every start)

Every anchor is asserted: an upstream change fails the build loudly instead of
silently publishing an image without the wrapper behaviour.
"""
import sys
from pathlib import Path


def patch_dockerfile(root: Path) -> None:
    path = root / "Dockerfile"
    text = path.read_text()

    engine = '["-DSTRATA_ENABLE_CUDA=ON", "-DSTRATA_Q6K_EXPERTS=ON", "-DSTRATA_MMQ_KQUANTS=ON", "-DSTRATA_BUILD_TESTS=OFF",'
    vision = '"-DSTRATA_VISION_CUDA=ON", "-DSTRATA_PORTABLE=OFF"'

    if engine not in text or vision not in text:
        raise SystemExit("Dockerfile build flags changed upstream; update docker/patch-upstream.py")

    text = text.replace(
        engine,
        '["-DSTRATA_ENABLE_CUDA=ON", "-DSTRATA_PORTABLE=ON", "-DSTRATA_Q6K_EXPERTS=ON", "-DSTRATA_MMQ_KQUANTS=ON", "-DSTRATA_BUILD_TESTS=OFF",',
        1,
    )
    text = text.replace(vision, '"-DSTRATA_VISION_CUDA=ON", "-DSTRATA_PORTABLE=ON"', 1)
    path.write_text(text)


def patch_entrypoint(root: Path) -> None:
    path = root / "docker-entrypoint.sh"
    text = path.read_text()

    config_anchor = 'CONFIG="${CONFIG:-}"'
    setup_anchor = '  if [ -n "$KV" ]; then set -- "$@" --kv "$KV"; fi'
    start_anchor = 'set -- --port "$PORT"\n'
    avx_anchor = 'if [ -r "$cpuinfo" ] && grep -q \'^flags\' "$cpuinfo"'

    if config_anchor not in text or setup_anchor not in text or start_anchor not in text or avx_anchor not in text:
        raise SystemExit("docker-entrypoint.sh changed upstream; update docker/patch-upstream.py")

    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith(config_anchor):
            lines.insert(i + 1, '\nDRAFT_VOCAB="${DRAFT_VOCAB:-}"    # en | cyrillic | fr | cjk: the draft layer token subset\n')
            break
    else:
        raise SystemExit("CONFIG line disappeared; update docker/patch-upstream.py")
    text = "".join(lines)

    text = text.replace(
        avx_anchor,
        'if [ "$(uname -m)" = "x86_64" ] && [ -r "$cpuinfo" ] && grep -q \'^flags\' "$cpuinfo"',
        1,
    )
    text = text.replace(
        setup_anchor,
        setup_anchor + '\n  if [ -n "$DRAFT_VOCAB" ]; then set -- "$@" --draft-vocab "$DRAFT_VOCAB"; fi',
        1,
    )
    override = (
        '# Wrapper config overrides: PREFILL, CONVERSATION_CACHE_MIB, FIT_MAX_TOKENS, SAMPLING_*.\n'
        'target="${CONFIG:-}"\n'
        'if [ -z "$target" ]; then\n'
        '  if [ "${keep:-}" = "1" ]; then\n'
        '    target="$(readlink -f "$link" 2>/dev/null || true)"\n'
        '    [ -n "$target" ] || target="$cfg"\n'
        '  else\n'
        '    ln -sfn "$cfg" "$link"\n'
        '    target="$cfg"\n'
        '  fi\n'
        'fi\n'
        '.venv/bin/python /opt/strata/strata-env-config.py "$target"\n\n'
    )
    text = text.replace(start_anchor, override + start_anchor, 1)
    text = text.replace(
        start_anchor,
        start_anchor + 'if [ -n "$DRAFT_VOCAB" ]; then set -- "$@" --draft-vocab "$DRAFT_VOCAB"; fi\n',
        1,
    )
    path.write_text(text)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    portable = "--portable" in sys.argv[2:]
    if portable:
        patch_dockerfile(root)
    patch_entrypoint(root)
    print(f"patched {root}" + (" (portable x86_64 build)" if portable else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
