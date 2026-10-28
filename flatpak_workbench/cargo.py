"""Cargo-specific inspection and standard Flatpak module generation."""

import hashlib
import json
import re
import shlex
import tomllib
from pathlib import Path

from .process import WorkbenchError, require


def metadata(root):
    return json.loads(require(["cargo", "metadata", "--offline", "--no-deps",
                               "--format-version", "1", "--manifest-path",
                               str(root / "Cargo.toml")], root))


def summarize(root):
    data = metadata(root)
    return [{"package": item["name"], "rust_version": item.get("rust_version"),
             "binaries": [target["name"] for target in item["targets"] if "bin" in target["kind"]],
             "features": sorted(item["features"])} for item in data["packages"]]


def validate(root, package, binary):
    data = metadata(root)
    if Path(data["workspace_root"]).resolve() != root:
        raise WorkbenchError("The Cargo workspace must be rooted at the checkout root.")
    for item in data["packages"]:
        if not Path(item["manifest_path"]).resolve().is_relative_to(root):
            raise WorkbenchError(f"Workspace member outside checkout: {item['manifest_path']}")
        for target in item["targets"]:
            if not Path(target["src_path"]).resolve().is_relative_to(root):
                raise WorkbenchError(f"Target source outside checkout: {target['src_path']}")
        for dependency in item["dependencies"]:
            if dependency.get("path") and not Path(dependency["path"]).resolve().is_relative_to(root):
                raise WorkbenchError(f"Path dependency outside checkout: {dependency['path']}")
    choices = [(item, target) for item in data["packages"] for target in item["targets"]
               if "bin" in target["kind"] and (not package or item["name"] == package)
               and (not binary or target["name"] == binary)]
    if len(choices) != 1:
        raise WorkbenchError("Select one executable with --package and --bin; use inspect to list candidates.")
    lock = root / "Cargo.lock"
    if not lock.is_file():
        raise WorkbenchError("A committed Cargo.lock is required.")
    packages = tomllib.loads(lock.read_text()).get("package", [])
    for item in packages:
        source = item.get("source")
        if source is None:
            continue
        if source != "registry+https://github.com/rust-lang/crates.io-index":
            raise WorkbenchError(f"Unsupported Cargo source for {item['name']}: {source}")
        if not re.fullmatch(r"[0-9a-f]{64}", item.get("checksum", "")):
            raise WorkbenchError(f"Missing/invalid checksum for {item['name']}")
    return choices[0][0], choices[0][1]


def module(package, binary, features, source_url, commit, installs, app_id):
    command = ["cargo", "build", "--offline", "--locked", "--release",
               "--package", package, "--bin", binary]
    if features:
        command.extend(["--features", ",".join(features)])
    commands = [shlex.join(command),
                shlex.join(["install", "-Dm755", f"target/release/{binary}", f"/app/bin/{binary}"])]
    for source, destination in installs:
        commands.append(shlex.join(["install", "-Dm644", source, destination]))
    return {
        "name": app_id, "buildsystem": "simple",
        "build-options": {"append-path": "/usr/lib/sdk/rust-stable/bin", "env": {
            "CARGO_HOME": f"/run/build/{app_id}/cargo", "CARGO_NET_OFFLINE": "true",
            "CARGO_TARGET_DIR": "target"}},
        "build-commands": commands,
        "sources": [{"type": "git", "url": source_url, "commit": commit}, "cargo-sources.json"],
    }


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
