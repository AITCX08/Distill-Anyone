"""Errors shared by platform selection and adapters."""


class PlatformError(RuntimeError):
    """Base class for actionable platform errors."""


class DuplicatePlatformError(PlatformError):
    def __init__(self, name: str):
        super().__init__(f"Platform is already registered: {name}")


class UnknownPlatformError(PlatformError):
    def __init__(self, name: str):
        super().__init__(f"Unknown platform: {name}")


class PlatformNotDetectedError(PlatformError):
    def __init__(self, target: str):
        super().__init__(f"No registered platform accepts target: {target}")


class AmbiguousPlatformError(PlatformError):
    def __init__(self, target: str, names: list[str]):
        choices = ", ".join(sorted(names))
        super().__init__(f"Multiple platforms accept target {target}: {choices}")


class TargetMismatchError(PlatformError):
    def __init__(self, platform: str, target: str):
        super().__init__(f"Target is not valid for explicit platform {platform}: {target}")


class TargetResolutionError(PlatformError):
    """A target matched a platform but could not resolve to a creator."""


class PlatformDownloadError(PlatformError):
    """A platform adapter could not produce its required local assets."""


class PlatformAuthenticationError(PlatformError):
    """Interactive authentication failed or timed out."""


class PlatformDependencyError(PlatformError):
    """An optional platform runtime dependency is unavailable."""


class PlatformSessionBusyError(PlatformError):
    """A persistent browser profile is already owned by another task."""
