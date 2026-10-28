"""Evidence gathering; detecting a build system does not imply support for it."""

import xml.etree.ElementTree as ET
from pathlib import Path

from .process import WorkbenchError, run

MARKERS = {
    "Cargo.toml": "cargo", "meson.build": "meson", "CMakeLists.txt": "cmake",
    "pyproject.toml": "python", "setup.py": "python", "package.json": "node",
    "go.mod": "go", "configure.ac": "autotools",
}


def tracked_files(root):
    result = run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], root)
    if result.returncode:
        raise WorkbenchError("Inspection currently requires a Git checkout.")
    return sorted(set(filter(None, result.stdout.split("\0"))))


def inspect_checkout(checkout):
    root = Path(checkout).resolve()
    if not root.is_dir():
        raise WorkbenchError(f"Checkout does not exist: {root}")
    top = run(["git", "rev-parse", "--show-toplevel"], root)
    if top.returncode or Path(top.stdout.strip()).resolve() != root:
        raise WorkbenchError("Pass the root of the upstream Git checkout.")
    files = tracked_files(root)
    systems = [{"kind": MARKERS[Path(name).name], "path": name}
               for name in files if Path(name).name in MARKERS]
    metadata = []
    desktop_files = []
    for name in files:
        expanded_name = name
        while expanded_name.endswith(".in"):
            expanded_name = expanded_name[:-3]
        if expanded_name.endswith(".desktop"):
            desktop_files.append(name)
        if expanded_name.endswith((".metainfo.xml", ".appdata.xml")):
            try:
                document = ET.parse(root / name).getroot()
                metadata.append({"path": name, "app_id": document.findtext("id"),
                                 "name": document.findtext("name")})
            except (ET.ParseError, OSError) as error:
                metadata.append({"path": name, "error": str(error)})
    commit = run(["git", "rev-parse", "HEAD"], root)
    remote = run(["git", "remote", "get-url", "origin"], root)
    dirty = run(["git", "status", "--porcelain", "--untracked-files=all"], root)
    return {
        "schema_version": 1, "checkout": str(root),
        "commit": commit.stdout.strip() if not commit.returncode else None,
        "origin": remote.stdout.strip() if not remote.returncode else None,
        "dirty": bool(dirty.stdout), "build_systems": systems,
        "metadata": metadata,
        "desktop_files": desktop_files,
        "native_dependencies": {"status": "unknown", "reason":
            "Build scripts and transitive native requirements are not inferred; use probe for explicit pkg-config requirements."},
    }
