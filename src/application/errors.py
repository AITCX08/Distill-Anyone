"""Errors that presentation adapters can map to CLI exits or HTTP responses."""


class ApplicationError(RuntimeError):
    code = "application_error"


class JobNotFoundError(ApplicationError):
    code = "job_not_found"

    def __init__(self, job_id: str):
        super().__init__(f"Job not found: {job_id}")
        self.job_id = job_id


class JobAlreadyExistsError(ApplicationError):
    code = "job_already_exists"

    def __init__(self, job_id: str):
        super().__init__(f"A different job already exists at this creator location: {job_id}")
        self.job_id = job_id


class InvalidJobTransitionError(ApplicationError):
    code = "invalid_job_transition"

    def __init__(self, current: str, requested: str):
        super().__init__(f"Cannot transition job from {current} to {requested}")
        self.current = current
        self.requested = requested


class ItemNotRetryableError(ApplicationError):
    code = "item_not_retryable"

    def __init__(self, source_id: str, status: str):
        super().__init__(f"Item {source_id} is not retryable from {status}")
        self.source_id = source_id
        self.status = status


class PreviewChangedError(ApplicationError):
    code = "preview_changed"

    def __init__(self):
        super().__init__("Preview is stale; run preview again before creating the job")
