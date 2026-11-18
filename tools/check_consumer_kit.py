#!/usr/bin/env python3
"""Verify the exact vendored python-numpy-fenics consumer-kit identity."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "vendor" / "python-runtime-consumer-kit.upstream.json"
KIT = ROOT / "vendor" / "python-runtime-consumer-kit"
CHECKER = KIT / "tools" / "check-vendored-kit.py"


def main() -> int:
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    if pin.get("format_version") != 1:
        raise SystemExit("consumer-kit pin format_version must be 1")
    if pin.get("repository") != "precsim/python-numpy-fenics":
        raise SystemExit("consumer-kit pin references an unexpected producer")

    revision = pin.get("revision")
    digest = pin.get("tree_sha256")
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise SystemExit("consumer-kit pin revision is not a full Git SHA")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise SystemExit("consumer-kit pin tree_sha256 is invalid")
    if pin.get("file_count") != 28:
        raise SystemExit("consumer-kit pin file_count is unexpected")
    if not CHECKER.is_file():
        raise SystemExit("vendored consumer-kit checker is missing")

    subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(KIT), "--expect", digest],
        cwd=ROOT,
        check=True,
    )
    print(f"consumer_kit_revision={revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
