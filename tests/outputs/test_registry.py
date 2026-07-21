from dataclasses import dataclass
from pathlib import Path

import pytest

from src.outputs.base import (
    ArtifactKind,
    CorpusOutputContext,
    ItemOutputContext,
    OutputReceipt,
)
from src.outputs.errors import DuplicateOutputTargetError, UnknownOutputTargetError
from src.outputs.manager import OutputManager
from src.outputs.registry import OutputRegistry


@dataclass
class FakeTarget:
    name: str
    required: frozenset[ArtifactKind]

    def required_artifacts(self):
        return self.required

    def consume_item(self, context: ItemOutputContext):
        return OutputReceipt(self.name, context.item.source_id, Path(f"{self.name}.md"), "hash")

    def finalize(self, context: CorpusOutputContext):
        return OutputReceipt(self.name, "corpus", Path(f"{self.name}.md"), "hash")


def test_duplicate_output_registration_is_rejected():
    registry = OutputRegistry([FakeTarget("episodes", frozenset())])

    with pytest.raises(DuplicateOutputTargetError):
        registry.register(FakeTarget("episodes", frozenset()))


def test_get_unknown_output_is_actionable():
    with pytest.raises(UnknownOutputTargetError, match="missing"):
        OutputRegistry().get("missing")


def test_output_manager_unions_required_artifacts():
    manager = OutputManager(
        [
            FakeTarget("episodes", frozenset({ArtifactKind.CLEANED})),
            FakeTarget("skill", frozenset({ArtifactKind.KNOWLEDGE})),
        ]
    )

    assert manager.required_artifacts() == frozenset(
        {ArtifactKind.CLEANED, ArtifactKind.KNOWLEDGE}
    )
