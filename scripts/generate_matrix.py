#!/usr/bin/env python3
"""Generate build matrix from packages/*.yml, filtering by inputs and existing packages."""

import argparse
import json
import os
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
