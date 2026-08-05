"""Domain exceptions for the Futu service boundary."""


class FutuServiceError(RuntimeError):
    """Base error exposed by the Futu service."""


class FutuConfigurationError(FutuServiceError):
    """Raised when configuration violates the supported safety envelope."""


class FutuConnectionError(FutuServiceError):
    """Raised when FutuOpenD cannot be reached or a context cannot be opened."""


class FutuApiError(FutuServiceError):
    """Raised when the SDK returns a non-success result."""


class FutuSafetyError(FutuServiceError):
    """Raised when an operation fails a mandatory safety rule."""


class AccountSelectionError(FutuSafetyError):
    """Raised when a unique active CN simulated account cannot be selected."""


class InvalidSecurityCodeError(FutuSafetyError, ValueError):
    """Raised when a security code does not match a supported A-share format."""
