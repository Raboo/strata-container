# Strata container images

Prebuilt, multi-arch-CUDA container images of [Niko1221/Strata](https://github.com/Niko1221/Strata), published to the GitHub Container Registry.

Upstream ships a [`Dockerfile`](https://github.com/Niko1221/Strata/blob/main/Dockerfile) but no images. This repository builds that Dockerfile at every upstream tagged release and publishes the result as a package:

```
ghcr.io/raboo/strata
```

<!-- latest-release -->
Current image: `ghcr.io/raboo/strata:0.1.44` (upstream release `v0.1.44`)
<!-- /latest-release -->

## Tags

| Tag | Meaning |
| --- | --- |
| `latest` | Most recent non-prerelease upstream release |
| `0.1.45` | Upstream version (`v` prefix stripped) |
| `v0.1.45` | Upstream git tag, verbatim |

Supports `linux/amd64` only (the image contains CUDA binaries).

## Run

```sh
docker run --rm --gpus all \
  -p 8080:8080 \
  --ulimit memlock=-1 \
  -v strata-data:/data \
  -e MODEL=IQ2_XS \
  ghcr.io/raboo/strata:latest
```

The first start downloads the model (~70 GB) into the `strata-data` volume and then serves the OpenAI/Anthropic-compatible API on `:8080`. Later starts go straight to serving.

Requirements and behaviour are upstream's:

- NVIDIA driver **>= 580** and `nvidia-container-toolkit` on the host.
- 12+ GB VRAM (two or three cards can share one model; see upstream `docs/MULTI_GPU.md`).
- Setup choices are environment variables (`FAMILY`, `MODEL`, `CONTEXT`, `VISION`, `KV`, `GPU`/`GPUS`, `LOW_RAM`, `HOST`, `PORT`, `API_KEY`, `GGUF_DIR`, ...). See the upstream Dockerfile header for the full list.
- Set `-e API_KEY=<secret>` before exposing the port.
- In a RAM-capped container pass `-e LOW_RAM=on`; `setup.py` reads the host's `/proc/meminfo`, not the container limit.
- Use `-e REINSTALL=1` to change the model settings later.

Model weights are **not** baked into the image; they are downloaded at runtime. Image size is therefore dominated by the CUDA toolchain and the prebuilt engine (several GB).

### Package visibility

New GHCR packages are private by default, and GitHub's REST API has no endpoint to change package visibility. If an anonymous `docker pull` is rejected, set the package to public in its [package settings](https://github.com/users/Raboo/packages/container/strata/settings) (Danger Zone → Change visibility). The `verify` job reports whether anonymous pulls work.

## How builds work

`.github/workflows/publish.yml`:

1. Every 6 hours (and on manual dispatch) resolves the latest upstream release; a dispatch can name any tag and force a rebuild.
2. Skips the build when `ghcr.io/raboo/strata:<version>` already exists, so the schedule is idempotent.
3. Checks out upstream at the tag, builds its `Dockerfile` with the portability patch below, and pushes the version, `v`-tag and (for the latest release) `latest`.
4. Verifies the pushed tags are readable in the registry (and whether anonymous pulls work, i.e. whether the package is public).
5. For the latest release, updates the version marker at the top of this README and commits it.

Scheduled workflows in public repositories are disabled after 60 days without a commit (the scheduled run itself does not count). `.github/workflows/keepalive.yml` runs weekly and commits a marker when the last commit is older than 50 days, so the release poll stays enabled even if upstream goes quiet; release builds also commit the README marker. Re-enable a disabled workflow from the Actions tab if it was off for longer than that.

### Deliberate deviations from upstream's Dockerfile

- **AVX2 CPU baseline.** Upstream's Dockerfile compiles native code for the build machine. A GitHub runner may have AVX-512, which would make the published image crash with `SIGILL` on AVX2-only CPUs — even though the image's entry point advertises AVX2 as the floor. The workflow injects `-DSTRATA_PORTABLE=ON` into both the engine and vision builds. If upstream changes those build flags, the patch step fails loudly instead of silently publishing a native image.
- **CUDA architectures** stay at upstream's default: `75;80;86;89;120` (RTX 20/30/40/50 and A-series). The engine is a fat binary and picks the matching cubin at runtime. For a card outside that set, build locally with `--build-arg CUDA_ARCHITECTURES=<arch>`.

### Rebuilding / building other tags

```sh
gh workflow run publish.yml --repo raboo/strata-container -f tag=v0.1.45 -f force=true
```

Scheduled workflows are disabled by GitHub after 60 days without repository activity; run the workflow manually (or push a commit) to re-enable it.

## License

The image repackages MIT-licensed software from [Niko1221/Strata](https://github.com/Niko1221/Strata). See that repository's `LICENSE`.
