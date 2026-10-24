# Strata container images

Prebuilt container images of [Niko1221/Strata](https://github.com/Niko1221/Strata), published to the GitHub Container Registry, built from upstream's signed engine component packages and Terminal sources at each tagged release.

```
ghcr.io/raboo/strata
```

<!-- latest-release -->
Current image: `ghcr.io/raboo/strata:0.2.4` (upstream release `v0.2.4`)
<!-- /latest-release -->

## Images

| Backend | Tags | Engines inside | Hardware |
| --- | --- | --- | --- |
| CUDA | `latest`, `0.2.1`, `v0.2.1` | CUDA 13 + CUDA 12 | RTX 20/30/40/50, A-series; GTX 10 / P100 / V100 through CUDA 12 |
| ROCm | `latest-rocm`, `0.2.1-rocm`, `v0.2.1-rocm` | `gfx120x` + `gfx110x` + `gfx1151` | RX 9000 / R9700, RX 7000 (and RX 7600), Ryzen AI Max (Strix Halo) |

All images are `linux/amd64`. One image per backend family contains every engine package; the Terminal picks the one that fits the card and driver at start. This is a deliberate difference from upstream's per-flavor tags (`0.2.1-cuda13`, `0.2.1-rocm-gfx120x`, ...).

Not covered by 0.2.1: AMD RX 6000 (`gfx1030`) has no package in the new release — keep using `0.1.45-rocm` for those cards. There is no Intel SYCL engine package in 0.2.1, so the newest Intel image remains `0.1.45-sycl`. Old tags are never deleted.

## Run

NVIDIA:

```sh
docker run -d --name strata --gpus all -p 127.0.0.1:8080:8080 \
  --ulimit memlock=-1:-1 --shm-size 2g --stop-timeout 120 \
  -v strata-data:/data -e MODEL=IQ3_XXS -e API_KEY=$(openssl rand -hex 24) \
  ghcr.io/raboo/strata:latest
```

AMD:

```sh
docker run -d --name strata --device /dev/kfd --device /dev/dri \
  --group-add video --group-add $(getent group render | cut -d: -f3) \
  -p 127.0.0.1:8080:8080 --ulimit memlock=-1:-1 --shm-size 2g --stop-timeout 120 \
  -v strata-data:/data -e MODEL=IQ3_XXS -e API_KEY=$(openssl rand -hex 24) \
  ghcr.io/raboo/strata:latest-rocm
```

Host requirements: NVIDIA driver **580+** for the CUDA 13 engine (575–579 uses CUDA 12) and `nvidia-container-toolkit`; AMD needs the `amdgpu` kernel driver (the image carries the ROCm runtime), `/dev/kfd` and `/dev/dri`. The model downloads into the `strata-data` volume on the first start; later starts reuse it.

Upstream 0.2.1 settings are environment variables (`MODEL`, `FAMILY`, `MODEL_PATH`, `CONTEXT`, `PARALLEL`, `VISION`, `KV`, `GPU`/`GPUS`, `TUNE`, `API_KEY`/`API_KEY_FILE`, `PORT`, `PRESET`, `STRATA_SET`). See upstream [`docs/DOCKER.md`](https://github.com/Niko1221/Strata/blob/main/docs/DOCKER.md).

The 0.1.x variables (`REINSTALL`, `LOW_RAM`, `CONFIG`, `GGUF_DIR`, `LAYER_SPLIT`, `RESIDENT_BUDGET_GIB`, `KV_STREAMING`, `HOST`) are **ignored** by the 0.2.1 entry point. Use `MODEL_PATH` instead of `GGUF_DIR`; the data layout is now `/data/Strata-data` and `/data/install`.

## Wrapper-only overrides

These are this repository's additions. The helper `docker/wrapper_env.py` is injected into the Terminal and applies them to the installed run config (`/data/install/strata-<model>.json`) on every launch — before the server starts. Values are persisted, so a later start without the variables keeps them; unset variables leave the config untouched. Invalid values abort the start with the expected range.

| Variable | Effect |
| --- | --- |
| `PREFILL` | `--prefill` in the config's `user_args` (`auto`, `auto:32768`, `2048`, ...) |
| `CONVERSATION_CACHE_MIB` | `--conversation-cache-mib` in `user_args` (positive integer) |
| `SAMPLING_TEMPERATURE` | `sampling.temperature` (number >= 0) |
| `SAMPLING_TOP_P` | `sampling.top_p` (0 < value <= 1) |
| `SAMPLING_TOP_K` | `sampling.top_k` (integer 1..64) |
| `SAMPLING_MIN_P` | `sampling.min_p` (0 <= value <= 1) |
| `SAMPLING_PRESENCE_PENALTY` | `sampling.presence_penalty` (number >= 0) |
| `SAMPLING_REPETITION_PENALTY` | `sampling.repetition_penalty` (number > 0; 1 = off) |
| `SAMPLING_FREQUENCY_PENALTY` | `sampling.frequency_penalty` (number >= 0) |
| `SAMPLING_PENALTY_LAST_N` | `sampling.penalty_last_n` (integer >= 0) |
| `SAMPLING_SEED` | `sampling.seed` (integer > 0) |
| `DRAFT_VOCAB` | draft layer's token subset (`cjk`, `en`, `cyrillic`, `fr`); copies the subset into the MTP folder |

```sh
docker run ... \
  -e PREFILL=auto:32768 \
  -e CONVERSATION_CACHE_MIB=8192 \
  -e SAMPLING_TEMPERATURE=1.0 \
  -e SAMPLING_TOP_P=0.95 \
  -e SAMPLING_TOP_K=20 \
  -e SAMPLING_MIN_P=0.0 \
  -e SAMPLING_PRESENCE_PENALTY=0.0 \
  -e SAMPLING_REPETITION_PENALTY=1.0 \
  -e DRAFT_VOCAB=en \
  ghcr.io/raboo/strata:latest
```

`DRAFT_VOCAB=en` frees about 215 MiB of graphics memory (348 MiB `cjk` → 133 MiB `en`); it only applies to models with an MTP draft layer. Sampling values are defaults for requests that leave the field out; a request's own value still wins. For any other advanced setting, upstream's `STRATA_SET` (`prefill=65536 STRATA_PIN_BY_NEED=1`) still works.

## Platform coverage

| Target | Available? |
| --- | --- |
| NVIDIA RTX 20–50 / A-series, amd64 | yes |
| NVIDIA GTX 10 / P100 / V100, amd64 | yes, through the CUDA 12 engine |
| AMD RX 9000 / R9700, RX 7000, Strix Halo, amd64 | yes |
| AMD RX 6000 (`gfx1030`), amd64 | not in 0.2.1 — use `0.1.45-rocm` |
| Intel Arc A/B, amd64 | not in 0.2.1 — use `0.1.45-sycl` |
| arm64 (DGX Spark, Grace) | no — upstream's engines are x86_64-only |
| NVIDIA Jetson (Orin/Thor) | no — L4T/JetPack stack, no upstream port |
| Apple Silicon / macOS | no — Metal is a native build, not a container |

The 0.2.1 engine packages are `linux-x86_64`; the arm64 build fails in upstream's host code (`immintrin.h`, AVX kernels). The old 0.1.45 images remain available for Intel, `gfx1030`, and anyone pinning the previous series.

## How builds work

`.github/workflows/publish.yml`:

1. Every 6 hours (and on manual dispatch) resolves the latest upstream release; a dispatch can name any tag and force a rebuild.
2. Builds the two backend families in parallel, skipping a family whose tag already exists.
3. Checks out upstream at the tag, copies `docker/wrapper_env.py` into `strata_cli/launch/`, and patches `strata_cli/launch/runner.py:build_config` so the wrapper variables are applied to the installed run config (`docker/patch-terminal.py` asserts the upstream anchors).
4. Fetches the release's signed engine packages with upstream's `docker/fetch-engines.py` (Ed25519-signed feed, SHA-256, package signatures, per-file hashes).
5. Builds with upstream's `docker/build.sh`: the Terminal is compiled from the tag's sources, the engines are installed, and the runtime image gets upstream's entrypoint, healthcheck and `/data` layout.
6. Smoke-tests the image (`strata --version`, wrapper module and patch present) and pushes the version, `v`-tag and `latest` (for the latest release).
7. Verifies every tag in the registry (and anonymous pulls). For the latest release, updates the version marker at the top of this README.

Scheduled workflows in public repositories are disabled after 60 days without a commit (the scheduled run itself does not count). `.github/workflows/keepalive.yml` runs weekly and commits a marker when the last commit is older than 50 days.

### Rebuilding

```sh
gh workflow run publish.yml --repo raboo/strata-container -f tag=v0.2.1 -f force=true
```

`force` rebuilds both backend families. The image is assembled from upstream's release packages; there is no local `docker build` recipe in this repository. For source builds of other flavors, use upstream's `docker/build.sh` and `docs/DOCKER.md`.

## License

The images repackage MIT-licensed software from [Niko1221/Strata](https://github.com/Niko1221/Strata). See that repository's `LICENSE`.
