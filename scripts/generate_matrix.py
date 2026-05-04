#!/usr/bin/env python3
"""Generate build matrix from variants.yaml, filtering by inputs and existing packages."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


def load_variants(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_combinations(variants: dict) -> list[dict]:
    """Expand variants.yaml into list of {cuda, pytorch, python} combos."""
    zip_keys = variants.get("zip_keys", [])
    cuda_versions = variants["cuda_compiler_version"]
    pytorch_versions = variants["pytorch"]
    python_versions = variants["python"]

    # cuda and pytorch are zipped together
    cuda_torch_pairs = list(zip(cuda_versions, pytorch_versions))

    combos = []
    for cuda, pytorch in cuda_torch_pairs:
        for python in python_versions:
            combos.append({
                "cuda": cuda,
                "pytorch": pytorch,
                "python": python,
            })
    return combos


def get_packages(package_input: str) -> list[str]:
    """Get list of packages to build."""
    recipes_dir = Path(__file__).parent.parent / "recipes"
    if package_input == "all":
        return [d.name for d in recipes_dir.iterdir() if d.is_dir() and (d / "recipe.yaml").exists()]
    return [package_input]


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
    # Simple parse — look for version: "X.Y.Z" in context
    for line in content.splitlines():
        if "version:" in line and '"' in line:
            return line.split('"')[1]
    return "0.0.0"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", required=True)
    parser.add_argument("--package", default="all")
    parser.add_argument("--cuda", default="all")
    parser.add_argument("--python", default="all")
    parser.add_argument("--pytorch", default="all")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--channel", default="pozzettiandrea")
    args = parser.parse_args()

    variants = load_variants(args.variants)
    combos = get_combinations(variants)
    packages = get_packages(args.package)

    # Filter by inputs
    if args.cuda != "all":
        combos = [c for c in combos if c["cuda"] == args.cuda]
    if args.python != "all":
        combos = [c for c in combos if c["python"] == args.python]
    if args.pytorch != "all":
        combos = [c for c in combos if c["pytorch"] == args.pytorch]

    matrix = []
    for package in packages:
        version = get_package_version(package)
        for combo in combos:
            cuda_short = combo["cuda"].replace(".", "")
            torch_short = combo["pytorch"].replace(".", "")
            py_short = combo["python"].replace(".", "")
            build_prefix = f"cu{cuda_short}_torch{torch_short}_py{py_short}"

            if not args.overwrite:
                if check_existing(args.channel, package, version, build_prefix):
                    print(f"  SKIP {package} {build_prefix} (exists)", file=sys.stderr)
                    continue

            matrix.append({
                "package": package,
                "cuda": combo["cuda"],
                "python": combo["python"],
                "pytorch": combo["pytorch"],
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
