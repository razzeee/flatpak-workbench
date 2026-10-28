"""External commands and persistent evidence, shared by all ecosystems."""

import json
import subprocess
from pathlib import Path


class WorkbenchError(Exception):
    pass


def run(argv, cwd=None, timeout=120):
    try:
        return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise WorkbenchError(f"Timed out after {timeout}s: {' '.join(argv)}") from error
    except OSError as error:
        raise WorkbenchError(f"Cannot run {argv[0]}: {error}") from error


def require(argv, cwd=None):
    result = run(argv, cwd)
    if result.returncode:
        raise WorkbenchError(f"{' '.join(argv)} failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def recorded_run(directory, name, argv, cwd=None, timeout=120):
    try:
        result = run(argv, cwd, timeout=timeout)
        record = {"command": argv, "cwd": str(cwd) if cwd else None,
                  "exit_code": result.returncode}
        stdout, stderr = result.stdout, result.stderr
    except WorkbenchError as error:
        record = {"command": argv, "exit_code": None, "invocation_error": str(error)}
        stdout, stderr = "", str(error)
    (directory / f"{name}.stdout").write_text(stdout)
    (directory / f"{name}.stderr").write_text(stderr)
    write_json(directory / f"{name}.json", record)
    return record, stdout
