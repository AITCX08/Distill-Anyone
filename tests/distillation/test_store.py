import json
import os
from unittest.mock import Mock

import pytest

from src.distillation.artifacts import ArtifactValidationError
from src.distillation.store import atomic_write_bytes, atomic_write_json


def test_atomic_json_fsyncs_then_replaces(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    replace = Mock(wraps=os.replace)
    fsync = Mock(wraps=os.fsync)
    monkeypatch.setattr(os, "replace", replace)
    monkeypatch.setattr(os, "fsync", fsync)

    atomic_write_json(target, {"schema_version": 1})

    assert json.loads(target.read_text("utf-8"))["schema_version"] == 1
    replace.assert_called_once()
    assert fsync.call_count >= 1
    assert not list(tmp_path.glob("*.tmp"))

def test_validation_failure_keeps_previous_file(tmp_path):
    target = tmp_path / "artifact.bin"
    target.write_bytes(b"previous")

    with pytest.raises(ArtifactValidationError):
        atomic_write_bytes(target, b"broken", validator=lambda path: False)

    assert target.read_bytes() == b"previous"
    assert not list(tmp_path.glob("*.tmp"))

