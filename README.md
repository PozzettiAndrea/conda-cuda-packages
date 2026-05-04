# conda-cuda-packages

Conda packages for CUDA Python extensions, built from source with `rattler-build`.

## Channel

```
https://conda.anaconda.org/pozzettiandrea
```

## Usage with pixi

```toml
[project]
channels = ["conda-forge", "https://conda.anaconda.org/pozzettiandrea"]

[dependencies]
cc_torch = "*"
torch_generic_nms = "*"
```

## Packages

| Package | Source | Description |
|---------|--------|-------------|
| cc_torch | [ronghanghu/cc_torch](https://github.com/ronghanghu/cc_torch) | Connected Components for PyTorch (CUDA) |
| torch_generic_nms | [ronghanghu/torch_generic_nms](https://github.com/ronghanghu/torch_generic_nms) | Generic Non-Maximum Suppression for PyTorch (CUDA) |

## CPU stubs

`cc_torch` and `torch_generic_nms` ship a `noarch: generic` CPU stub alongside the real GPU builds (`recipes/{cc_torch,torch_generic_nms}_stub/`). The stub installs no Python module — `import cc_torch` raises `ModuleNotFoundError` — and uses `track_features` to deprioritize itself versus the real builds.

Solver behavior:
- **GPU host** (`__cuda` virtual present): real GPU build wins, real symbols available.
- **CPU host**: GPU builds filtered out by the missing `__cuda`, stub is the only candidate. `import` fails so consumer code falls back to its CPU implementation.

Build the stubs from the GitHub Actions workflow with `package: stubs`. They only need rebuilding when bumping the version.

## Build

```bash
# Real GPU build (one combo)
rattler-build build --recipe recipes/cc_torch/recipe.yaml --variant-config variants.yaml --channel conda-forge

# CPU stub (single noarch artifact)
rattler-build build --recipe recipes/cc_torch_stub/recipe.yaml --channel conda-forge
```
