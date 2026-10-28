"""Flatpak SDK probes and build/lint feedback shared across build systems."""

import json
import tempfile
from pathlib import Path

from .process import WorkbenchError, recorded_run, run, write_json


def lint_result(record, stdout):
    if record["exit_code"] is None:
        return {**record, "status": "tool-error"}
    if not stdout.strip():
        return {**record, "status": "passed" if record["exit_code"] == 0 else "tool-error"}
    try:
        findings = json.loads(stdout)
    except ValueError:
        return {**record, "status": "tool-error", "reason": "Linter output was not JSON"}
    if not isinstance(findings, dict):
        return {**record, "status": "tool-error", "reason": "Unexpected linter output shape"}
    return {**record, "status": "findings" if record["exit_code"] else "passed", "findings": findings}


def check(manifest, runs):
    manifest = Path(manifest).resolve()
    # JSON is the initial editable manifest format. Included fragments remain Builder's responsibility.
    data = json.loads(manifest.read_text())
    runs = Path(runs).resolve()
    runs.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="check-", dir=runs))
    permissions = [f"--filesystem={manifest.parent}", f"--filesystem={directory}"]
    prefix = ["flatpak", "run", *permissions]
    results = {}
    identity, stdout = recorded_run(directory, "builder-identity",
                                    ["flatpak", "info", "--show-commit", "org.flatpak.Builder"])
    results["builder"] = {**identity, "commit": stdout.strip()}
    lint = prefix + ["--command=flatpak-builder-lint", "org.flatpak.Builder"]
    record, stdout = recorded_run(directory, "manifest-lint", lint + ["manifest", str(manifest)], manifest.parent)
    results["manifest-lint"] = lint_result(record, stdout)
    prerequisites = []
    for field in ("runtime", "sdk"):
        ref = f"{data[field]}//{data['runtime-version']}"
        record, stdout = recorded_run(directory, field, ["flatpak", "info", "--show-commit", ref])
        prerequisites.append({**record, "ref": ref, "commit": stdout.strip(),
                              "hint": f"flatpak install flathub {ref}" if record["exit_code"] else None})
    results["prerequisites"] = prerequisites
    if identity["exit_code"] != 0 or any(item["exit_code"] != 0 for item in prerequisites):
        results["build"] = {"status": "blocked", "reason": "Install missing Builder/runtime/SDK refs; see prerequisites."}
    else:
        builddir, repo = directory / "builddir", directory / "repo"
        command = prefix + ["org.flatpak.Builder", f"--state-dir={directory / 'state'}",
                            f"--repo={repo}", str(builddir), str(manifest)]
        record, _ = recorded_run(directory, "build", command, manifest.parent, timeout=None)
        results["build"] = {**record, "status": "passed" if record["exit_code"] == 0 else "failed"}
        if record["exit_code"] == 0:
            for mode, artifact in (("builddir", builddir), ("repo", repo)):
                record, stdout = recorded_run(directory, f"{mode}-lint", lint + [mode, str(artifact)], manifest.parent)
                results[f"{mode}-lint"] = lint_result(record, stdout)
    results["success"] = results["build"]["status"] == "passed" and all(
        result["status"] == "passed" for key, result in results.items() if key.endswith("-lint"))
    results["run_directory"] = str(directory)
    write_json(directory / "result.json", results)
    return results


def probe(sdk, requirements):
    identity = run(["flatpak", "info", "--show-commit", sdk])
    results = []
    for requirement in requirements:
        if identity.returncode:
            results.append({"requirement": requirement, "status": "unknown", "reason": identity.stderr.strip()})
            continue
        # Reserve 42 for a missing requirement; ordinary launch/tool failures stay unknown.
        script = 'command -v pkg-config >/dev/null || exit 43; pkg-config --exists "$1" || exit 42; pkg-config --modversion "$1"'
        command = ["flatpak", "run", "--command=sh", sdk, "-c", script, "probe", requirement]
        try:
            result = run(command, timeout=10)
        except WorkbenchError as error:
            results.append({"requirement": requirement, "status": "unknown", "reason": str(error)})
            continue
        status = {0: "present", 42: "missing"}.get(result.returncode, "unknown")
        results.append({"requirement": requirement, "status": status, "command": command,
                        "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
    return {"sdk": sdk, "sdk_commit": identity.stdout.strip() if not identity.returncode else None,
            "scope": "Build SDK only; runtime availability and completeness of requirements are not established.",
            "requirements": results}
