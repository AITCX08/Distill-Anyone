"""Coordinate selected targets without recomputing shared artifacts."""

from collections.abc import Iterable

from src.outputs.base import (
    ArtifactKind,
    CorpusOutputContext,
    ItemOutputContext,
    OutputReceipt,
    OutputTarget,
)


class OutputManager:
    def __init__(self, targets: Iterable[OutputTarget]):
        self._targets = tuple(targets)

    def required_artifacts(self) -> frozenset[ArtifactKind]:
        required: set[ArtifactKind] = set()
        for target in self._targets:
            required.update(target.required_artifacts())
        return frozenset(required)

    def consume_item(self, context: ItemOutputContext) -> tuple[OutputReceipt, ...]:
        receipts = (target.consume_item(context) for target in self._targets)
        return tuple(receipt for receipt in receipts if receipt is not None)

    def finalize(self, context: CorpusOutputContext) -> tuple[OutputReceipt, ...]:
        receipts = (target.finalize(context) for target in self._targets)
        return tuple(receipt for receipt in receipts if receipt is not None)
