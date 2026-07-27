"""Output target and artifact writing errors."""


class OutputError(RuntimeError):
    """Base class for output failures."""


class DuplicateOutputTargetError(OutputError):
    def __init__(self, name: str):
        super().__init__(f"Output target is already registered: {name}")


class UnknownOutputTargetError(OutputError):
    def __init__(self, name: str):
        super().__init__(f"Unknown output target: {name}")


class OutputValidationError(OutputError):
    def __init__(self, path):
        super().__init__(f"Output validation failed before replace: {path}")
