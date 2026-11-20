from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TARGETS = {"win-x64", "linux-x64", "macos-arm64", "macos-x64"}
PROFILES = {"core", "numpy", "fenics"}
EXPECTED_EXPORTS = [
    "mexFunction",
    "mexfilerequiredapiversion",
    "__octave_mex_soversion__",
]
EXPECTED_SOURCES = {
    "src/mock_bridge.c",
    "src/mock_host.c",
    "src/mock_host.h",
    "src/mock_platform.c",
    "src/mock_platform.h",
    "src/mock_python.c",
    "src/mock_python.h",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConsumerContractTests(unittest.TestCase):
    def test_vendored_consumer_kit_identity(self) -> None:
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "check_consumer_kit.py")],
            cwd=ROOT,
            check=True,
        )

    def test_bridge_manifest_uses_only_the_mock_surface(self) -> None:
        manifest = json.loads((ROOT / "bridge-build.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["format_version"], 1)
        self.assertEqual(manifest["mex_name"], "bridge")
        self.assertEqual(set(manifest["sources"]), {path for path in EXPECTED_SOURCES if path.endswith(".c")})
        self.assertEqual(manifest["include_dirs"], ["src"])
        self.assertEqual(manifest["python_helpers"], ["python/mock_backend.py"])
        self.assertEqual(manifest["host_fixtures"], ["host/mock_smoke.m"])
        self.assertEqual(set(manifest["targets"]), TARGETS)
        for target in manifest["targets"].values():
            self.assertEqual(target["exports"], EXPECTED_EXPORTS)

        actual_sources = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "src").iterdir()
            if path.is_file()
        }
        self.assertEqual(actual_sources, EXPECTED_SOURCES)

        build_tool = load_module(
            "consumer_build_bridge",
            ROOT / "vendor" / "python-runtime-consumer-kit" / "tools" / "build_bridge.py",
        )
        for target in TARGETS:
            _, sources, include_dirs = build_tool.load_build(
                ROOT / "bridge-build.json", ROOT, target
            )
            self.assertEqual(len(sources), 4)
            self.assertEqual(include_dirs, [(ROOT / "src").resolve()])

        bridge_source = (ROOT / "src" / "mock_bridge.c").read_text(encoding="utf-8")
        platform_source = (ROOT / "src" / "mock_platform.c").read_text(encoding="utf-8")
        self.assertIn("mexfilerequiredapiversion", bridge_source)
        self.assertIn("pthread_self", platform_source)

    def test_runtime_receipt_pins_every_target_and_profile(self) -> None:
        receipt = json.loads(
            (ROOT / "locks" / "consumer" / "python-runtime-cp314.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(receipt["format_version"], 1)
        self.assertEqual(receipt["producer_repository"], "precsim/python-numpy-fenics")
        self.assertEqual(set(receipt["profiles"]), TARGETS)

        for target, records in receipt["profiles"].items():
            self.assertEqual(set(records), PROFILES, target)
            for profile in ("core", "numpy"):
                record = records[profile]
                self.assertEqual(record["release_tag"], "runtime-v0.1.0")
                self.assertEqual(
                    record["producer_revision"],
                    "91423af1a1ae36221440ccc2475c1c88758d6d9f",
                )
            fenics = records["fenics"]
            self.assertEqual(fenics["release_tag"], "runtime-v0.1.0")
            self.assertEqual(fenics["base"]["release_tag"], "runtime-v0.1.0-rc1")
            self.assertEqual(fenics["overlay"]["release_tag"], "runtime-v0.1.0")

    def test_scalar_backend_probe_is_deterministic_without_runtime_imports(self) -> None:
        backend = load_module("consumer_mock_backend", ROOT / "python" / "mock_backend.py")
        self.assertEqual(backend.scalar(5.0), 11.0)
        self.assertEqual(backend.scalar(10.0), 21.0)
        with self.assertRaises(TypeError):
            backend.scalar(5)

    def test_consumer_layout_places_mex_at_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            runtime = root / "verified-runtime"
            runtime.mkdir()
            (runtime / "runtime-manifest.json").write_text("{}\n", encoding="utf-8")
            nested = runtime / "lib" / "sentinel.txt"
            nested.parent.mkdir()
            nested.write_text("producer byte\n", encoding="utf-8")
            mex = root / "candidate.mex"
            mex.write_bytes(b"exact candidate")
            backend = root / "backend.py"
            backend.write_text("VALUE = 1\n", encoding="utf-8")
            fixture = root / "smoke.m"
            fixture.write_text("disp('ok');\n", encoding="utf-8")
            package = root / "package"
            record = root / "layout.json"

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "prepare_consumer_layout.py"),
                    "--runtime", str(runtime),
                    "--mex", str(mex),
                    "--profile", "numpy",
                    "--backend", str(backend),
                    "--host-fixture", str(fixture),
                    "--output", str(package),
                    "--record", str(record),
                ],
                check=True,
            )

            self.assertEqual((package / "bridge.mex").read_bytes(), mex.read_bytes())
            self.assertEqual((package / "lib" / "sentinel.txt").read_text(), "producer byte\n")
            self.assertEqual((package / "profile.txt").read_text(), "numpy\n")
            evidence = json.loads(record.read_text(encoding="utf-8"))
            self.assertEqual(evidence["runtime_root_model"], "mex-directory")
            if os.name != "nt":
                self.assertTrue((package / "runtime").is_symlink())
                self.assertEqual(os.readlink(package / "runtime"), ".")


if __name__ == "__main__":
    unittest.main()
