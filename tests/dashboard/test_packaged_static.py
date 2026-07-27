import json

import pytest

from scripts.build_dashboard import STATIC_DIR, publish_static_bundle, validate_static_bundle


def write_bundle(root, *, valid=True):
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<main>Dashboard</main>", encoding="utf-8")
    (root / "assets" / "index.js").write_text("console.log('safe')", encoding="utf-8")
    (root / "assets" / "index.css").write_text("body{}", encoding="utf-8")
    manifest = {
        "index.html": {
            "file": "assets/index.js" if valid else "assets/missing.js",
            "css": ["assets/index.css"],
            "isEntry": True,
        }
    }
    (root / ".vite").mkdir()
    (root / ".vite" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_publish_static_bundle_validates_manifest_and_atomically_replaces_static_dir(tmp_path):
    bundle = tmp_path / "dist"
    destination = tmp_path / "static"
    write_bundle(bundle)
    destination.mkdir()
    (destination / "stale.txt").write_text("old", encoding="utf-8")

    publish_static_bundle(bundle, destination)

    assert validate_static_bundle(destination) == {"assets/index.js", "assets/index.css"}
    assert (destination / "assets" / "index.js").is_file()
    assert not (destination / "stale.txt").exists()


def test_invalid_bundle_does_not_replace_existing_static_dir(tmp_path):
    bundle = tmp_path / "dist"
    destination = tmp_path / "static"
    write_bundle(bundle, valid=False)
    destination.mkdir()
    (destination / "known-good.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="missing asset"):
        publish_static_bundle(bundle, destination)

    assert (destination / "known-good.txt").read_text(encoding="utf-8") == "keep"


def test_committed_static_bundle_is_manifest_valid_without_node_runtime():
    assets = validate_static_bundle(STATIC_DIR)

    assert assets
    assert (STATIC_DIR / "index.html").is_file()
