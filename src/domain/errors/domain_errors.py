class DomainError(Exception):
    """Base exception class for domain errors."""

    def __init__(self, message: str) -> None:
        """Initialize the domain error with a message string."""
        super().__init__(message)
        self.message = message


class PolicyVersionMismatchError(DomainError):
    """Raised when an operation encounters a mismatch in policy version."""

    def __init__(self, message: str) -> None:
        """Initialize the policy version mismatch error with a message string."""
        super().__init__(message)


class InsufficientEvidenceError(DomainError):
    """Raised when there is insufficient policy evidence to complete claim adjudication."""

    def __init__(self, message: str) -> None:
        """Initialize the insufficient evidence error with a message string."""
        super().__init__(message)


class PolicyNotFoundError(DomainError):
    """Raised when a requested insurance policy cannot be found."""

    def __init__(self, message: str) -> None:
        """Initialize the policy not found error with a message string."""
        super().__init__(message)


class InvalidClaimStateError(DomainError):
    """Raised when an action is performed on a claim in an invalid state."""

    def __init__(self, message: str) -> None:
        """Initialize the invalid claim state error with a message string."""
        super().__init__(message)
