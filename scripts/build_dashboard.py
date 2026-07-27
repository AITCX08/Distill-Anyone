"""Build and validate the Dashboard static bundle for Python-only runtime."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / "dashboard"
DIST_DIR = DASHBOARD_DIR / "dist"
STATIC_DIR = ROOT / "src" / "dashboard" / "static"
MANIFEST = Path(".vite") / "manifest.json"


def _safe_asset_path(bundle: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("manifest asset path is unsafe")
    resolved = (bundle / candidate).resolve()
    if not resolved.is_relative_to(bundle.resolve()):
        raise ValueError("manifest asset path is unsafe")
    return resolved


def validate_static_bundle(bundle: Path) -> set[str]:
    """Return manifest-referenced assets after proving a bundle is self-contained."""

    index = bundle / "index.html"
    manifest_path = bundle / MANIFEST
    if not index.is_file():
        raise ValueError("dashboard bundle is missing index.html")
    if not manifest_path.is_file():
        raise ValueError("dashboard bundle is missing manifest")
    try:
        manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("dashboard manifest is malformed") from error
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("dashboard manifest is malformed")

    assets: set[str] = set()
    for entry in manifest.values():
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            raise ValueError("dashboard manifest entry is malformed")
        values = [entry["file"], *entry.get("css", ()), *entry.get("assets", ())]
        if not all(isinstance(value, str) for value in values):
            raise ValueError("dashboard manifest entry is malformed")
        for value in values:
            asset = _safe_asset_path(bundle, value)
            if not asset.is_file():
                raise ValueError(f"dashboard manifest references missing asset: {value}")
            assets.add(value)
    return assets


def publish_static_bundle(bundle: Path, destination: Path) -> None:
    """Validate first, then replace the served static directory through staging."""

    validate_static_bundle(bundle)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(tempfile.mkdtemp(prefix=".dashboard-static-", dir=destination.parent))
    staging = temporary_root / destination.name
    backup = destination.with_name(f".{destination.name}.previous")
    try:
        shutil.copytree(bundle, staging)
        validate_static_bundle(staging)
        if backup.exists():
            shutil.rmtree(backup)
        if destination.exists():
            os.replace(destination, backup)
        try:
            os.replace(staging, destination)
        except OSError:
            if backup.exists():
                os.replace(backup, destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def build_frontend() -> None:
    npm = os.environ.get("NPM", "npm.cmd" if os.name == "nt" else "npm")
    subprocess.run([npm, "run", "build"], cwd=DASHBOARD_DIR, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate committed static assets without Node")
    parser.add_argument("--from-dist", action="store_true", help="publish an existing dashboard/dist without running npm")
    args = parser.parse_args()
    if args.check and args.from_dist:
        parser.error("--check and --from-dist cannot be combined")
    if args.check:
        validate_static_bundle(STATIC_DIR)
        return 0
    if not args.from_dist:
        build_frontend()
    publish_static_bundle(DIST_DIR, STATIC_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
