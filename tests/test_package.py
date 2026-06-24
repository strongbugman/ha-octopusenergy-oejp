"""Tests for the manual Home Assistant install package."""

from __future__ import annotations

import json
from pathlib import Path
import zipfile

from scripts.package_integration import DOMAIN, build_package, is_forbidden_path


def test_package_zip_contains_manifest_and_excludes_forbidden_paths(tmp_path):
    zip_path, archive_names = build_package(dist_dir=tmp_path)

    manifest_file_path = Path("custom_components") / DOMAIN / "manifest.json"
    with open(manifest_file_path, "r", encoding="utf-8") as f:
        version = json.load(f)["version"]

    assert zip_path == tmp_path / f"{DOMAIN}-{version}.zip"
    assert archive_names == sorted(archive_names)

    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        manifest_path = f"custom_components/{DOMAIN}/manifest.json"

        assert names == archive_names
        assert manifest_path in names
        assert f"custom_components/{DOMAIN}/__init__.py" in names
        assert all(name.startswith(f"custom_components/{DOMAIN}/") for name in names)
        assert all("__pycache__" not in name for name in names)
        assert all(not name.endswith((".pyc", ".pyo")) for name in names)
        assert all("/tests/" not in name and not name.startswith("tests/") for name in names)
        assert all("/reports/" not in name and not name.startswith("reports/") for name in names)
        assert all("api.md" not in name for name in names)
        assert all(".env" not in name for name in names)
        assert all("secret" not in Path(name).name.lower() for name in names)
        for sample_identifier in (b"A-1234567", b"ESP-001", b"SP-0001", b"MSA-001"):
            assert all(sample_identifier not in archive.read(name) for name in names)

        manifest = json.loads(archive.read(manifest_path).decode("utf-8"))
        assert manifest["domain"] == DOMAIN
        assert "manifest.json" in manifest_path
        assert manifest["requirements"] == ["httpx>=0.27"]


def test_forbidden_path_filter_covers_sensitive_and_generated_files():
    forbidden = [
        Path("custom_components/octopusenergy_oejp/__pycache__/api.cpython-311.pyc"),
        Path("custom_components/octopusenergy_oejp/module.pyc"),
        Path("tests/test_api.py"),
        Path("reports/real_account_data_report.md"),
        Path("api.md"),
        Path(".env"),
        Path(".env.local"),
        Path("custom_components/octopusenergy_oejp/secrets.yaml"),
    ]
    allowed = [
        Path("custom_components/octopusenergy_oejp/manifest.json"),
        Path("custom_components/octopusenergy_oejp/sensor.py"),
        Path("custom_components/octopusenergy_oejp/strings.json"),
    ]

    assert all(is_forbidden_path(path) for path in forbidden)
    assert not any(is_forbidden_path(path) for path in allowed)


def test_hacs_manifest_is_minimal_valid_json():
    hacs_manifest = json.loads(Path("hacs.json").read_text(encoding="utf-8"))

    assert hacs_manifest.get("name") == "Octopus Energy OEJP"
