"""Export ordinary manifests, keeping choices and tool provenance alongside them."""

import json
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from . import cargo
from .inspect import inspect_checkout, tracked_files
from .process import WorkbenchError, recorded_run, require, write_json


def generate(args):
    root = Path(args.checkout).resolve()
    evidence = inspect_checkout(root)
    if evidence["dirty"] or not evidence["commit"]:
        raise WorkbenchError("Export requires a clean, committed checkout (including untracked files).")
    if not re.fullmatch(r"[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+\.[A-Za-z_][\w-]*", args.app_id, re.ASCII):
        raise WorkbenchError("Supply a reverse-DNS --app-id with at least three components.")
    if not (root / "Cargo.toml").is_file():
        raise WorkbenchError("Generation currently supports a root Cargo.toml; inspect supports other ecosystems.")
    outer = [system for system in evidence["build_systems"]
             if system["path"] in ("meson.build", "CMakeLists.txt", "configure.ac")]
    if outer:
        raise WorkbenchError("Detected an outer build system; plain Cargo generation would bypass it: "
                             + ", ".join(item["kind"] for item in outer))
    files = tracked_files(root)
    if "Cargo.lock" not in require(["git", "ls-files"], root).splitlines():
        raise WorkbenchError("Cargo.lock must be tracked in the source revision.")
    if any(name in files for name in (".cargo/config", ".cargo/config.toml")):
        raise WorkbenchError("Upstream Cargo configuration requires manual integration with vendored sources.")
    package, target = cargo.validate(root, args.package, args.bin)
    for feature in args.feature:
        if feature not in package["features"]:
            raise WorkbenchError(f"Unknown feature for {package['name']}: {feature}")
    url = args.source_url or evidence["origin"]
    if not url or urlparse(url).scheme != "https" or not urlparse(url).netloc:
        raise WorkbenchError("Supply a public HTTPS Git URL with --source-url.")
    installs = []
    for value in args.install:
        source, separator, destination = value.partition("=")
        if not separator or source not in files or not (root / source).resolve().is_relative_to(root):
            raise WorkbenchError(f"Install source must be a file inside the checkout: {value}")
        if not (root / source).is_file() or not destination.startswith("/app/") or ".." in Path(destination).parts:
            raise WorkbenchError(f"Install destination must be a file under /app: {value}")
        installs.append((source, destination))
    generator = Path(args.cargo_generator).resolve()
    if not generator.is_file():
        raise WorkbenchError(f"Cargo generator not found: {generator}")
    output = Path(args.output).absolute()
    if output.exists() or output.is_relative_to(root):
        raise WorkbenchError("Choose a new output directory outside the upstream checkout.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".workbench-", dir=output.parent) as temporary:
        stage = Path(temporary)
        command = ["uv", "run", "--no-project", "--script", str(generator),
                   str(root / "Cargo.lock"), "-o", str(stage / "cargo-sources.json")]
        record, _ = recorded_run(stage, "generator", command, stage, timeout=None)
        if record["exit_code"] != 0:
            # Keep failed generator evidence, but never a misleading manifest.
            stage.rename(output)
            raise WorkbenchError(f"Cargo generator failed; logs retained in {output}")
        sources = json.loads((stage / "cargo-sources.json").read_text())
        if not isinstance(sources, list):
            raise WorkbenchError("Cargo generator did not emit a source array.")
        manifest = {
            "app-id": args.app_id, "runtime": args.runtime, "runtime-version": args.runtime_version,
            "sdk": args.sdk, "sdk-extensions": ["org.freedesktop.Sdk.Extension.rust-stable"],
            "command": target["name"], "finish-args": args.finish_arg,
            "modules": [cargo.module(package["name"], target["name"], args.feature, url,
                                     evidence["commit"], installs, args.app_id)],
        }
        manifest_path = stage / f"{args.app_id}.json"
        write_json(manifest_path, manifest)
        write_json(stage / "provenance.json", {
            "schema_version": 1, "source_url": url, "source_commit": evidence["commit"],
            "lockfile_sha256": cargo.digest(root / "Cargo.lock"),
            "generator_sha256": cargo.digest(generator),
            "sources_sha256": cargo.digest(stage / "cargo-sources.json"),
            "manifest_sha256": cargo.digest(manifest_path),
        })
        (stage / "packaging-notes.md").write_text(
            f"# Packaging decisions for {args.app_id}\n\n"
            f"- Source: {url} at `{evidence['commit']}`.\n"
            f"- Cargo package `{package['name']}`, executable `{target['name']}` selected explicitly or uniquely.\n"
            f"- Enabled features: {', '.join(args.feature) or 'upstream defaults only'}.\n"
            f"- SDK `{args.sdk}//{args.runtime_version}` and runtime `{args.runtime}` supplied by the packager; not yet verified.\n"
            "- Rust extension follows the SDK's extension metadata, not the GNOME/KDE branch number.\n"
            "- Application and crate sources are pinned; runtime branches can move.\n"
            "- Offline dependencies generated by flatpak-builder-tools; generator digest is in provenance.json.\n"
            "- Desktop assets and permissions are explicit packager choices; inspect lists candidates.\n"
            "- Native dependency and runtime library availability remain unknown until probed/built.\n"
            "- Build/lint success has not been established by generation. Run `flatpak-workbench check`.\n")
        (stage / ".gitignore").write_text(".flatpak-builder/\n.workbench-runs/\nbuilddir/\nrepo/\n")
        stage.rename(output)
    return {"manifest": str(output / f"{args.app_id}.json"), "output": str(output)}
