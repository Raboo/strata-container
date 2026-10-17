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

| Backend | Tags | Hardware | Status |
| --- | --- | --- | --- |
| CUDA | `latest`, `0.1.45`, `v0.1.45` | NVIDIA RTX 20/30/40/50, A-series | upstream-supported |
| ROCm | `latest-rocm`, `0.1.45-rocm`, `v0.1.45-rocm` | AMD RX 7900/7800/7700/9070/9060/6800/6900 | upstream HIP backend |
| SYCL | `latest-sycl`, `0.1.45-sycl`, `v0.1.45-sycl` | Intel Arc A/B-series | experimental upstream port |

All images are `linux/amd64`. Each backend tag is independent: a missing or failed variant does not block the others.

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

Host requirements: the kernel's `amdgpu` driver; **no ROCm install is needed** (the image carries ROCm 7.2.4). Supported architectures: `gfx1100` (RX 7900), `gfx1101` (RX 7800/7700), `gfx1200` (RX 9060), `gfx1201` (RX 9070 / R9700), `gfx1030` (RX 6800/6900). Images on AMD use the CPU encoder only (`VISION=cpu`); one card per model.

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

### macOS

There is no Mac image, and GitHub Actions cannot make one. Containers are Linux; Docker on macOS runs them in a VM without Metal GPU passthrough, and macOS itself is not a container target. Upstream's Apple Silicon support is a native build (`metal/setup_mac.py`), not an image.

## How builds work

`.github/workflows/publish.yml`:

1. Every 6 hours (and on manual dispatch) resolves the latest upstream release; a dispatch can name any tag and force a rebuild.
2. Builds each variant whose `ghcr.io/raboo/strata:<version><suffix>` tag does not exist yet, so the schedule is idempotent.
3. CUDA builds upstream's `Dockerfile` with the portability patch below. ROCm and SYCL use `docker/Dockerfile.rocm` and `docker/Dockerfile.sycl` (upstream has no Dockerfile for either).
4. Verifies every expected tag is readable in the registry, and whether anonymous pulls work (i.e. whether the package is public).
5. For the latest release, updates the version marker at the top of this README and commits it.

Scheduled workflows in public repositories are disabled after 60 days without a commit (the scheduled run itself does not count). `.github/workflows/keepalive.yml` runs weekly and commits a marker when the last commit is older than 50 days, so the release poll stays enabled even if upstream goes quiet. Re-enable a disabled workflow from the Actions tab if it was off for longer than that.

### Backend recipes and deviations

- **CUDA / AVX2 CPU baseline.** Upstream's Dockerfile compiles native code for the build machine. A GitHub runner may have AVX-512, which would make the published image crash with `SIGILL` on AVX2-only CPUs — even though the entry point advertises AVX2 as the floor. The workflow injects `-DSTRATA_PORTABLE=ON` into both the engine and vision builds. If upstream changes those build flags, the patch step fails loudly instead of silently publishing a native image.
- **CUDA architectures** stay at upstream's default: `75;80;86;89;120` (RTX 20/30/40/50 and A-series). The engine is a fat binary and picks the matching cubin at runtime. For a card outside that set, build locally with `--build-arg CUDA_ARCHITECTURES=<arch>`.
- **ROCm** uses upstream's HIP build flags from `setup.py:build_engine_hip`, `rocm/dev-ubuntu-24.04:7.2.4`, and a fat binary for `gfx1100;gfx1101;gfx1200;gfx1201;gfx1030` (`--build-arg HIP_ARCHITECTURES=...` to narrow). `engine/BUILD.json` is written the way `setup.py` expects, so the first start reuses the engine instead of compiling. The CUDA entry point is reused unchanged.
- **SYCL** builds upstream's `sycl/` project on its documented oneAPI/Level Zero base with JIT (`--build-arg SYCL_AOT=bmg-g31` for AOT). The port's `sycl/serve/strata-sycl.sh` normally starts a nested `strata-sycl-dev` container; the image replaces it with a direct exec and keeps data under `/work`, which is the path its setup writes into configs.
- **Package visibility.** GHCR packages are private by default and GitHub's REST API cannot change visibility. If an anonymous pull fails, set the package to public in its [package settings](https://github.com/users/Raboo/packages/container/strata/settings) (Danger Zone → Change visibility). The `verify` job reports whether anonymous pulls work.

### Rebuilding / building other tags

```sh
gh workflow run publish.yml --repo raboo/strata-container -f tag=v0.1.45 -f force=true
```

`force` rebuilds all three variants. To build one locally, use an upstream checkout as the build context:

```sh
git clone --depth 1 --branch v0.1.45 https://github.com/Niko1221/Strata.git /tmp/strata
docker build -f docker/Dockerfile.rocm -t strata-rocm /tmp/strata
docker build -f docker/Dockerfile.sycl -t strata-sycl /tmp/strata
```

## License

The images repackage MIT-licensed software from [Niko1221/Strata](https://github.com/Niko1221/Strata). See that repository's `LICENSE`.
