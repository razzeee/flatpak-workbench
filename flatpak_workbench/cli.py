import argparse
import json
import sys
from pathlib import Path

from . import cargo
from .feedback import check, probe
from .generate import generate
from .inspect import inspect_checkout
from .process import WorkbenchError


def parser():
    root = argparse.ArgumentParser(description="Inspect upstream projects and produce ordinary Flatpak manifests.")
    commands = root.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Collect build-system and desktop metadata evidence")
    inspect.add_argument("checkout")
    init = commands.add_parser("init", help="Generate a pinned manifest for a Cargo executable")
    init.add_argument("checkout")
    for name in ("app-id", "runtime", "runtime-version", "sdk", "cargo-generator", "output"):
        init.add_argument(f"--{name}", required=True)
    for name in ("package", "bin", "source-url"):
        init.add_argument(f"--{name}")
    for name in ("feature", "finish-arg", "install"):
        init.add_argument(f"--{name}", action="append", default=[])
    verify = commands.add_parser("check", help="Build and lint, retaining logs for each phase")
    verify.add_argument("manifest")
    verify.add_argument("--runs", default=".workbench-runs")
    sdk = commands.add_parser("probe", help="Check explicit pkg-config requirements inside an SDK")
    sdk.add_argument("--sdk", required=True, help="Installed SDK ref, e.g. org.gnome.Sdk//49")
    sdk.add_argument("requirements", nargs="+")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_checkout(args.checkout)
            if (Path(args.checkout) / "Cargo.toml").is_file():
                try:
                    result["cargo"] = cargo.summarize(Path(args.checkout).resolve())
                except WorkbenchError as error:
                    result["cargo"] = {"error": str(error)}
        elif args.command == "init":
            result = generate(args)
        elif args.command == "check":
            result = check(args.manifest, args.runs)
        else:
            result = probe(args.sdk, args.requirements)
        print(json.dumps(result, indent=2))
        if args.command == "check" and not result["success"]:
            return 1
        if args.command == "probe" and any(item["status"] != "present" for item in result["requirements"]):
            return 1
        return 0
    except (WorkbenchError, OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
