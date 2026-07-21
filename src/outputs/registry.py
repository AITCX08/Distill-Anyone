"""Explicit registry for built-in output targets."""

from collections.abc import Iterable

from src.outputs.base import OutputTarget
from src.outputs.errors import DuplicateOutputTargetError, UnknownOutputTargetError


class OutputRegistry:
    def __init__(self, targets: Iterable[OutputTarget] = ()):
        self._targets: dict[str, OutputTarget] = {}
        for target in targets:
            self.register(target)

    def register(self, target: OutputTarget) -> None:
        if target.name in self._targets:
            raise DuplicateOutputTargetError(target.name)
        self._targets[target.name] = target

    def get(self, name: str) -> OutputTarget:
        try:
            return self._targets[name]
        except KeyError as exc:
            raise UnknownOutputTargetError(name) from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._targets))
