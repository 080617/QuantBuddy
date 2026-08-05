"""Execution adapter domain exceptions."""


class ExecutionAdapterError(RuntimeError):
    """Base adapter failure."""


class ArtifactError(ExecutionAdapterError):
    """An execution artifact is missing, malformed, or untrusted."""


class PlanningError(ExecutionAdapterError):
    """A deterministic plan could not be built or persisted."""
