# Strata container images

Prebuilt container images of [Niko1221/Strata](https://github.com/Niko1221/Strata), published to the GitHub Container Registry: NVIDIA CUDA, AMD Radeon (HIP), and Intel Arc (SYCL, experimental).

Upstream ships a [`Dockerfile`](https://github.com/Niko1221/Strata/blob/main/Dockerfile) but no images. This repository builds images at every upstream tagged release and publishes them as a package:

```
ghcr.io/raboo/strata
```

<!-- latest-release -->
Current image: `ghcr.io/raboo/strata:0.1.45` (upstream release `v0.1.45`)
<!-- /latest-release -->

## Images

| Backend | Tags | Platforms | Hardware | Status |
| --- | --- | --- | --- | --- |
| CUDA | `latest`, `0.1.45`, `v0.1.45`; arm64: `latest-arm64`, `0.1.45-arm64`, `v0.1.45-arm64` | `linux/amd64`, `linux/arm64` | NVIDIA RTX 20/30/40/50, A-series; DGX Spark (GB10, sm_121) | upstream-supported |
| ROCm | `latest-rocm`, `0.1.45-rocm`, `v0.1.45-rocm` | `linux/amd64` | AMD RX 7900/7800/7700/7600/9070/9060/6800/6900; Strix Halo (gfx1151) | upstream HIP backend |
| SYCL | `latest-sycl`, `0.1.45-sycl`, `v0.1.45-sycl` | `linux/amd64` | Intel Arc A/B-series | experimental upstream port |

Canonical CUDA tags are multi-arch manifests (amd64 + arm64); the `-arm64` tags are the explicit arm64 builds. Each backend tag is independent: a missing or failed variant does not block the others.

## Run

### NVIDIA (CUDA)

```sh
docker run --rm --gpus all \
  -p 8080:8080 \
  --ulimit memlock=-1 \
  -v strata-data:/data \
  -e MODEL=IQ2_XS \
  ghcr.io/raboo/strata:latest
```

Host requirements: NVIDIA driver **>= 580** and `nvidia-container-toolkit`.

### NVIDIA DGX Spark (arm64)

The canonical CUDA tags are multi-arch; on a DGX Spark they resolve to the arm64 image built for GB10 (`sm_121`). The explicit tag is `latest-arm64`.

```sh
docker run --rm --gpus all \
  -p 8080:8080 \
  --ulimit memlock=-1 \
  -v strata-data:/data \
  -e MODEL=IQ2_XS \
  ghcr.io/raboo/strata:latest
```

Host requirements: DGX OS (arm64), NVIDIA driver and `nvidia-container-toolkit`. The arm64 image carries CUDA code for `sm_121` only; it is not a general-purpose arm64 GPU image.

### AMD (ROCm)

```sh
docker run --rm \
  --device /dev/kfd --device /dev/dri \
  --group-add video --group-add render \
  -p 8080:8080 --ulimit memlock=-1 \
  -v strata-data:/data \
  -e MODEL=IQ2_XS \
  ghcr.io/raboo/strata:latest-rocm
```

Host requirements: the kernel's `amdgpu` driver; **no ROCm install is needed** (the image carries ROCm 7.2.4). Supported architectures: `gfx1100` (RX 7900), `gfx1101` (RX 7800/7700), `gfx1102` (RX 7600), `gfx1200` (RX 9060), `gfx1201` (RX 9070 / R9700), `gfx1030` (RX 6800/6900), and `gfx1151` (Ryzen AI Max "Strix Halo", experimental). Images on AMD use the CPU encoder only (`VISION=cpu`); one card per model.

Strix Halo is an APU with unified memory: the engine treats the GPU's GTT pool as its VRAM, so give it as much GTT as your BIOS/kernel allows (`ttm.pages_limit`, upstream `docs/STRIX_HALO.md`). Upstream validates gfx1151 with ROCm 7.14; this image carries 7.2.4, whose rocBLAS includes gfx1151 kernels but whose hipBLASLt has no matching tuning table, so prompt GEMMs fall back to plain hipBLAS.

### Intel Arc (SYCL) — experimental

```sh
docker run --rm --device /dev/dri \
  -p 8080:8080 \
  -v strata-data:/work/data \
  -e MODEL=IQ2_XS \
  ghcr.io/raboo/strata:latest-sycl
```

Host requirements: the `xe` or `i915` kernel driver plus Intel's compute runtime (`intel-opencl-icd libze1 libze-intel-gpu1`). The data volume is `/work/data` here, not `/data`. Built as SPIR-V (JIT), so it runs on A- and B-series cards; the first start JIT-compiles kernels (~47 s). Images are not wired on Intel yet. Treat it as experimental: upstream has no Intel GPU and validates the port on community hardware.

### Common behaviour

The first start downloads the model (~70 GB) into the data volume and then serves the OpenAI/Anthropic-compatible API on `:8080`. Later starts go straight to serving.

- Setup choices are environment variables (`FAMILY`, `MODEL`, `CONTEXT`, `KV`, `HOST`, `PORT`, `API_KEY`, `GGUF_DIR`, ...). See the upstream Dockerfile header for the full CUDA list; the AMD and SYCL images pass the same core variables.
- Set `-e API_KEY=<secret>` before exposing the port.
- `-e REINSTALL=1` re-runs setup to change model settings.
- `-e DRAFT_VOCAB=en` selects the draft layer's token subset. The default `cjk` needs up to ~348 MiB of VRAM; `en` (English and code) needs ~133 MiB, `cyrillic` ~193 MiB, `fr` ~151 MiB. The choice is stored in the model config and reused on later starts; models without an MTP draft layer ignore it.
- Model weights are **not** baked into the images; they are downloaded at runtime.

### Wrapper-only overrides

These edit the model config before the server starts, so they persist on later starts (unset them to keep the last value):

| Variable | Config effect |
| --- | --- |
| `PREFILL` | `--prefill <value>` in `args` (`auto`, `auto:32768`, `2048`, ...) |
| `CONVERSATION_CACHE_MIB` | `--conversation-cache-mib <MiB>` in `args` (positive integer, added if absent) |
| `FIT_MAX_TOKENS` | top-level `"fit_max_tokens": true` or `false` |
| `SAMPLING_TEMPERATURE` | `sampling.temperature` (number >= 0) |
| `SAMPLING_TOP_P` | `sampling.top_p` (0 < value <= 1) |
| `SAMPLING_TOP_K` | `sampling.top_k` (integer 1..64) |
| `SAMPLING_MIN_P` | `sampling.min_p` (0 <= value <= 1) |
| `SAMPLING_PRESENCE_PENALTY` | `sampling.presence_penalty` (number >= 0) |
| `SAMPLING_REPETITION_PENALTY` | `sampling.repetition_penalty` (number > 0; 1 = off) |
| `SAMPLING_FREQUENCY_PENALTY` | `sampling.frequency_penalty` (number >= 0) |
| `SAMPLING_PENALTY_LAST_N` | `sampling.penalty_last_n` (integer >= 0) |
| `SAMPLING_SEED` | `sampling.seed` (integer > 0) |

```sh
docker run ... \
  -e PREFILL=auto:32768 \
  -e CONVERSATION_CACHE_MIB=8192 \
  -e FIT_MAX_TOKENS=true \
  -e SAMPLING_TEMPERATURE=1.0 \
  -e SAMPLING_TOP_P=0.95 \
  -e SAMPLING_TOP_K=20 \
  -e SAMPLING_MIN_P=0.0 \
  -e SAMPLING_PRESENCE_PENALTY=0.0 \
  -e SAMPLING_REPETITION_PENALTY=1.0 \
  ghcr.io/raboo/strata:latest
```

Sampling values are defaults for requests that leave the field out; a request's own value still wins. Invalid values fail the container start with the expected range. Aliases `repeat_penalty` / `repeat_last_n` are replaced by the canonical keys when overridden.

### Platform coverage

| Target | Available? |
| --- | --- |
| NVIDIA RTX 20–50 / A-series, amd64 | yes |
| NVIDIA DGX Spark GB10, arm64 (`sm_121`) | yes |
| AMD Radeon RX 6000/7000/9000, amd64 | yes |
| AMD Strix Halo (`gfx1151`), amd64 | yes (experimental upstream) |
| Intel Arc A/B-series, amd64 | yes (experimental upstream) |
| AMD ROCm on arm64 | no — no consumer Radeon/ROCm arm64 target |
| Intel Arc on arm64 | no — x86-only platform |
| NVIDIA Jetson (Orin/Thor) | no — L4T/JetPack's CUDA stack differs; upstream has no port |
| Apple Silicon / macOS | no — Linux containers cannot use Metal |

macOS cannot be a container target: Docker runs Linux containers in a VM without Metal GPU passthrough, and upstream's Apple Silicon support is a native build (`metal/setup_mac.py`). The arm64 CUDA image exists for DGX Spark, not for Macs.

## How builds work

`.github/workflows/publish.yml`:

1. Every 6 hours (and on manual dispatch) resolves the latest upstream release; a dispatch can name any tag and force a rebuild.
2. Builds each variant whose `ghcr.io/raboo/strata:<version><suffix>` tag does not exist yet, so the schedule is idempotent.
3. CUDA builds upstream's `Dockerfile` on amd64 (`--portable`) and on arm64 for DGX Spark (`sm_121`). ROCm and SYCL use `docker/Dockerfile.rocm` and `docker/Dockerfile.sycl` (upstream has no Dockerfile for either).
4. Combines the amd64 and arm64 CUDA manifests under the canonical tags (`0.1.45`, `v0.1.45`, `latest`).
5. Verifies every expected tag is readable in the registry, and whether anonymous pulls work (i.e. whether the package is public).
6. For the latest release, updates the version marker at the top of this README and commits it.

Scheduled workflows in public repositories are disabled after 60 days without a commit (the scheduled run itself does not count). `.github/workflows/keepalive.yml` runs weekly and commits a marker when the last commit is older than 50 days, so the release poll stays enabled even if upstream goes quiet. Re-enable a disabled workflow from the Actions tab if it was off for longer than that.

### Backend recipes and deviations

- **CUDA / AVX2 CPU baseline (amd64 only).** Upstream's Dockerfile compiles native code for the build machine. A GitHub runner may have AVX-512, which would make the published image crash with `SIGILL` on AVX2-only CPUs — even though the entry point advertises AVX2 as the floor. The amd64 build injects `-DSTRATA_PORTABLE=ON` into both the engine and vision builds; the arm64 build stays native. `docker/patch-upstream.py` also exposes `DRAFT_VOCAB` and the config overrides, and limits the AVX2 warning to `x86_64`. Every upstream anchor is asserted, so an upstream change fails the build loudly.
- **CUDA architectures.** amd64 stays at upstream's default `75;80;86;89;120` (RTX 20/30/40/50 and A-series). arm64 is built with `CUDA_ARCHITECTURES=121` for DGX Spark (GB10). Both are fat binaries/cubins; a card outside the set needs a local build with `--build-arg CUDA_ARCHITECTURES=<arch>`.
- **ROCm** uses upstream's HIP build flags from `setup.py:build_engine_hip`, `rocm/dev-ubuntu-24.04:7.2.4`, and a fat binary for `gfx1100;gfx1101;gfx1102;gfx1200;gfx1201;gfx1030;gfx1151` (`--build-arg HIP_ARCHITECTURES=...` to narrow). `engine/BUILD.json` is written the way `setup.py` expects, so the first start reuses the engine instead of compiling. The CUDA entry point is reused unchanged.
- **SYCL** builds upstream's `sycl/` project on its documented oneAPI/Level Zero base with JIT (`--build-arg SYCL_AOT=bmg-g31` for AOT). The port's `sycl/serve/strata-sycl.sh` normally starts a nested `strata-sycl-dev` container; the image replaces it with a direct exec and keeps data under `/work`, which is the path its setup writes into configs.
- **Package visibility.** GHCR packages are private by default and GitHub's REST API cannot change visibility. If an anonymous pull fails, set the package to public in its [package settings](https://github.com/users/Raboo/packages/container/strata/settings) (Danger Zone → Change visibility). The `verify` job reports whether anonymous pulls work.

### Rebuilding / building other tags

```sh
gh workflow run publish.yml --repo raboo/strata-container -f tag=v0.1.45 -f force=true
```

`force` rebuilds all variants (amd64 CUDA, arm64 CUDA, ROCm, SYCL). To build locally, use an upstream checkout as the build context and run the same patch helper:

```sh
git clone --depth 1 --branch v0.1.45 https://github.com/Niko1221/Strata.git /tmp/strata-amd64
git clone --depth 1 --branch v0.1.45 https://github.com/Niko1221/Strata.git /tmp/strata-arm64
cp docker/strata-env-config.py /tmp/strata-amd64/ /tmp/strata-arm64/

# CUDA amd64 (AVX2 baseline)
python3 docker/patch-upstream.py /tmp/strata-amd64 --portable
docker build -f /tmp/strata-amd64/Dockerfile -t strata /tmp/strata-amd64

# CUDA arm64 (DGX Spark, sm_121; needs an arm64 host)
python3 docker/patch-upstream.py /tmp/strata-arm64
docker build -f /tmp/strata-arm64/Dockerfile --build-arg CUDA_ARCHITECTURES=121 -t strata-arm64 /tmp/strata-arm64

# ROCm and SYCL (their Dockerfiles carry the entry point patch)
cp docker/strata-env-config.py /tmp/strata-amd64/
docker build -f docker/Dockerfile.rocm -t strata-rocm /tmp/strata-amd64
docker build -f docker/Dockerfile.sycl -t strata-sycl /tmp/strata-amd64
```

## License

The images repackage MIT-licensed software from [Niko1221/Strata](https://github.com/Niko1221/Strata). See that repository's `LICENSE`.
