#!/usr/bin/env python3
"""Generate build matrix from packages/*.yml, filtering by inputs and existing packages."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml


def load_package_config(package: str) -> dict:
    path = Path(__file__).parent.parent / "packages" / f"{package}.yml"
    with open(path) as f:
        return yaml.safe_load(f)


PLATFORM_MAP = {
    "linux": {"runner": "ubuntu-latest", "subdir": "linux-64"},
    "windows": {"runner": "windows-latest", "subdir": "win-64"},
}


def get_combinations(config: dict) -> list[dict]:
    """Expand package config into list of {cuda, pytorch, python, platform} combos."""
    platforms = config.get("build_matrix", {}).get("platforms", ["linux"])
    combos = []
    for entry in config["build_matrix"]["combinations"]:
        for py in entry["python_versions"]:
            for platform in platforms:
                if platform not in PLATFORM_MAP:
                    continue
                combos.append({
                    "cuda": entry["cuda"],
                    "pytorch": entry["pytorch"],
                    "python": py,
                    "platform": platform,
                    "runner": PLATFORM_MAP[platform]["runner"],
                    "subdir": PLATFORM_MAP[platform]["subdir"],
                })
    return combos


def get_packages(package_input: str) -> list[str]:
    """Get list of packages to build."""
    packages_dir = Path(__file__).parent.parent / "packages"
    if package_input == "all":
        return [p.stem for p in packages_dir.glob("*.yml")]
    return [package_input]


_PYPI_PATCH_CACHE: dict = {}


def resolve_pytorch_full_version(pytorch_minor: str, cuda: str, python: str, platform: str) -> str | None:
    """Find the latest pip torch wheel matching this (minor, cuda, python, platform).

    Returns the full version (e.g. '2.10.4') or None if no matching wheel exists
    on download.pytorch.org. The full version is needed by the build script to
    construct the wheel download URL; the minor goes into the runtime dep.
    """
    cuda_short = cuda.replace(".", "")
    py_tag = f"cp{python.replace('.', '')}"
    cache_key = (pytorch_minor, cuda_short, py_tag, platform)
    if cache_key in _PYPI_PATCH_CACHE:
        return _PYPI_PATCH_CACHE[cache_key]

    plat_re = "(?:manylinux_2_28_x86_64|linux_x86_64)" if platform == "linux" else "win_amd64"
    pattern = re.compile(
        rf"torch-({re.escape(pytorch_minor)}\.\d+(?:\.post\d+)?)\+cu{cuda_short}-{py_tag}-{py_tag}-{plat_re}\.whl"
    )

    url = f"https://download.pytorch.org/whl/cu{cuda_short}/torch/"
    try:
        result = subprocess.run(
            ["curl", "-sf", url], capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            _PYPI_PATCH_CACHE[cache_key] = None
            return None
        candidates = sorted(set(pattern.findall(result.stdout)), key=_version_key, reverse=True)
        full = candidates[0] if candidates else None
    except (subprocess.TimeoutExpired, Exception):
        full = None

    _PYPI_PATCH_CACHE[cache_key] = full
    return full


def _version_key(v: str):
    """Sort key for version strings like '2.10.4' or '2.10.0.post1'."""
    parts = v.replace(".post", ".").split(".")
    return tuple(int(p) if p.isdigit() else 0 for p in parts)


def check_existing(channel: str, package: str, version: str, build_string_prefix: str) -> bool:
    """Check if a package with matching build string exists on anaconda.org."""
    url = f"https://api.anaconda.org/package/{channel}/{package}/files"
    try:
        result = subprocess.run(
            ["curl", "-sf", url],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return False
        files = json.loads(result.stdout)
        for f in files:
            basename = f.get("basename", "")
            if build_string_prefix in basename and f.get("version") == version:
                return True
    except (json.JSONDecodeError, subprocess.TimeoutExpired, Exception):
        pass
    return False


def get_package_version(package: str) -> str:
    """Read version from recipe.yaml."""
    recipe_path = Path(__file__).parent.parent / "recipes" / package / "recipe.yaml"
    with open(recipe_path) as f:
        content = f.read()
    for line in content.splitlines():
        if "version:" in line and '"' in line:
            return line.split('"')[1]
    return "0.0.0"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", required=False, help="(unused, kept for compat)")
    parser.add_argument("--package", default="all")
    parser.add_argument("--cuda", default="all")
    parser.add_argument("--python", default="all")
    parser.add_argument("--pytorch", default="all")
    parser.add_argument("--platform", default="all")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--channel", default="pozzettiandrea")
    args = parser.parse_args()

    packages = get_packages(args.package)

    matrix = []
    for package in packages:
        config = load_package_config(package)
        version = get_package_version(package)
        combos = get_combinations(config)

        # Filter by inputs
        if args.cuda != "all":
            combos = [c for c in combos if c["cuda"] == args.cuda]
        if args.python != "all":
            combos = [c for c in combos if c["python"] == args.python]
        if args.pytorch != "all":
            combos = [c for c in combos if c["pytorch"] == args.pytorch]
        if args.platform != "all":
            combos = [c for c in combos if c["platform"] == args.platform]

        for combo in combos:
            # Resolve the latest matching pip torch patch for this (cuda, python, platform).
            # The build script needs the full version (e.g. 2.10.4) to construct the wheel
            # download URL; the runtime dep uses the minor (combo['pytorch']) for the
            # `pytorch X.Y.*` matchspec.
            pytorch_full = resolve_pytorch_full_version(
                combo["pytorch"], combo["cuda"], combo["python"], combo["platform"]
            )
            if pytorch_full is None:
                print(
                    f"  SKIP {package} cu{combo['cuda']}/py{combo['python']}/torch{combo['pytorch']}/{combo['platform']} "
                    f"(no matching pip torch wheel on download.pytorch.org)",
                    file=sys.stderr,
                )
                continue

            build_prefix = f"cu{combo['cuda']}_torch{combo['pytorch']}_py{combo['python']}_{combo['subdir']}"

            if not args.overwrite:
                if check_existing(args.channel, package, version, build_prefix):
                    print(f"  SKIP {package} {build_prefix} (exists)", file=sys.stderr)
                    continue

            matrix.append({
                "package": package,
                "cuda": combo["cuda"],
                "python": combo["python"],
                "pytorch": combo["pytorch"],
                "pytorch_full": pytorch_full,
                "platform": combo["platform"],
                "runner": combo["runner"],
                "subdir": combo["subdir"],
            })

    print(f"  {len(matrix)} builds in matrix", file=sys.stderr)

    # Output for GitHub Actions
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    matrix_json = json.dumps(matrix)
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"matrix={matrix_json}\n")
    else:
        print(f"matrix={matrix_json}")


if __name__ == "__main__":
    main()
