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

## Build

```bash
rattler-build build --recipe recipes/cc_torch/recipe.yaml --variant-config variants.yaml --channel conda-forge
```
