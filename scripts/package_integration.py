#!/usr/bin/env python3
"""Build a manual-install zip for the Octopus Energy OEJP HA integration."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path


DOMAIN = "octopusenergy_oejp"
PACKAGE_ROOT = Path("custom_components") / DOMAIN
DEFAULT_DIST_DIR = Path("dist")

FORBIDDEN_DIR_PARTS = {
    "__pycache__",
    ".git",
    ".local",
    ".pytest_cache",
    ".venv",
    "reports",
    "tests",
}
FORBIDDEN_FILE_NAMES = {
    ".env",
    "api.md",
}
FORBIDDEN_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def repo_root() -> Path:
    """Return the repository root based on this script's location."""
    return Path(__file__).resolve().parent.parent


def is_forbidden_path(path: Path) -> bool:
    """Return True when a path must not be included in the install zip."""
    parts = set(path.parts)
    name = path.name
    lower_name = name.lower()
    return (
        bool(parts & FORBIDDEN_DIR_PARTS)
        or name in FORBIDDEN_FILE_NAMES
        or name.startswith(".env")
        or lower_name.startswith("secrets")
        or "secret" in lower_name
        or path.suffix in FORBIDDEN_SUFFIXES
    )


def _manifest_version(root: Path) -> str:
    manifest_path = root / PACKAGE_ROOT / "manifest.json"
    with manifest_path.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{manifest_path} must define a non-empty string version")
    return version


def package_members(root: Path) -> list[Path]:
    """Return source files to include, relative to the repository root."""
    source_dir = root / PACKAGE_ROOT
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Integration directory not found: {source_dir}")

    members: list[Path] = []
    for file_path in sorted(source_dir.rglob("*")):
        if not file_path.is_file():
            continue
        relative_path = file_path.relative_to(root)
        if is_forbidden_path(relative_path):
            continue
        members.append(relative_path)

    manifest_path = PACKAGE_ROOT / "manifest.json"
    if manifest_path not in members:
        raise FileNotFoundError(f"Package would not include required file: {manifest_path}")
    return members


def build_package(
    *,
    root: Path | None = None,
    dist_dir: Path | None = None,
    zip_name: str | None = None,
) -> tuple[Path, list[str]]:
    """Create the install zip and return its path plus archive member names."""
    root = (root or repo_root()).resolve()
    version = _manifest_version(root)
    dist_dir = root / (dist_dir or DEFAULT_DIST_DIR)
    zip_name = zip_name or f"{DOMAIN}-{version}.zip"
    zip_path = dist_dir / zip_name

    dist_dir.mkdir(parents=True, exist_ok=True)
    archive_names: list[str] = []

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path in package_members(root):
            archive_name = relative_path.as_posix()
            zip_info = zipfile.ZipInfo(archive_name, date_time=(1980, 1, 1, 0, 0, 0))
            zip_info.compress_type = zipfile.ZIP_DEFLATED
            zip_info.external_attr = 0o644 << 16
            archive.writestr(zip_info, (root / relative_path).read_bytes())
            archive_names.append(archive_name)

    return zip_path, archive_names


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Home Assistant manual-install zip under dist/."
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=DEFAULT_DIST_DIR,
        help="Directory for the generated zip, relative to the repo root unless absolute.",
    )
    parser.add_argument(
        "--zip-name",
        help=f"Output zip filename. Defaults to {DOMAIN}-<manifest version>.zip.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = repo_root()
    dist_dir = args.dist_dir if args.dist_dir.is_absolute() else root / args.dist_dir
    zip_path, archive_names = build_package(
        root=root,
        dist_dir=dist_dir,
        zip_name=args.zip_name,
    )

    print(f"Created {zip_path}")
    print(f"Included {len(archive_names)} files:")
    for archive_name in archive_names:
        print(f"  {archive_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
