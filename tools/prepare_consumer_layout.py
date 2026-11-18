#!/usr/bin/env python3
"""Compose a disposable bridge package around a verified producer runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise SystemExit(f"required input is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if sha256(source) != sha256(destination):
        raise SystemExit(f"copy changed file bytes: {source} -> {destination}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--mex", type=Path, required=True)
    parser.add_argument("--profile", choices=("core", "numpy", "fenics"), required=True)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--host-fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()

    runtime = args.runtime.resolve()
    output = args.output.resolve()
    if not runtime.is_dir():
        raise SystemExit(f"verified runtime directory is missing: {runtime}")
    if output.exists():
        raise SystemExit(f"consumer layout already exists: {output}")

    shutil.copytree(runtime, output, symlinks=True)
    copy_file(args.mex.resolve(), output / "bridge.mex")
    copy_file(args.backend.resolve(), output / "python" / "mock_backend.py")
    copy_file(args.host_fixture.resolve(), output / "host" / "mock_smoke.m")
    (output / "profile.txt").write_text(args.profile + "\n", encoding="utf-8")

    # The vendored host launcher uses package/runtime only to locate FEniCS
    # process-global native providers. The real bridge runtime root is the MEX
    # directory itself, so POSIX layouts expose that launcher compatibility
    # path as a self-relative symlink without duplicating producer bytes.
    if os.name != "nt":
        compatibility = output / "runtime"
        if compatibility.exists() or compatibility.is_symlink():
            raise SystemExit("producer runtime unexpectedly contains a top-level runtime entry")
        compatibility.symlink_to(".", target_is_directory=True)

    record = {
        "format_version": 1,
        "profile": args.profile,
        "runtime_source": str(runtime),
        "package_root": str(output),
        "runtime_root_model": "mex-directory",
        "mex_sha256": sha256(output / "bridge.mex"),
        "backend_sha256": sha256(output / "python" / "mock_backend.py"),
        "host_fixture_sha256": sha256(output / "host" / "mock_smoke.m"),
    }
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"consumer_layout={output}")
    print(f"consumer_layout_mex_sha256={record['mex_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
