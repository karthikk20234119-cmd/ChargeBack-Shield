"""
Razorpay API Client — Structured Error Hierarchy

These exceptions represent specific Razorpay API failure modes.
They carry safe metadata only — never credentials or raw responses.
"""


class RazorpayClientError(Exception):
    """Base exception for all Razorpay API client errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        dispute_id: str | None = None,
        raw_error_code: str | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.dispute_id = dispute_id
        self.raw_error_code = raw_error_code
        super().__init__(message)


class RazorpayAuthenticationError(RazorpayClientError):
    """401 — Invalid or missing API credentials."""

    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message=message, status_code=401, **kwargs)


class RazorpayNotFoundError(RazorpayClientError):
    """404 — Requested dispute or resource not found."""

    def __init__(self, message: str = "Resource not found", **kwargs):
        super().__init__(message=message, status_code=404, **kwargs)


class RazorpayRateLimitError(RazorpayClientError):
    """429 — Rate limit exceeded. May include retry_after seconds."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
        **kwargs,
    ):
        self.retry_after = retry_after
        super().__init__(message=message, status_code=429, **kwargs)


class RazorpayValidationError(RazorpayClientError):
    """400 — Request validation failed on Razorpay's side."""

    def __init__(self, message: str = "Validation error", **kwargs):
        super().__init__(message=message, status_code=400, **kwargs)


class RazorpayServerError(RazorpayClientError):
    """5xx — Razorpay server-side error."""

    def __init__(self, message: str = "Server error", status_code: int = 500, **kwargs):
        super().__init__(message=message, status_code=status_code, **kwargs)


class RazorpayNetworkError(RazorpayClientError):
    """Network-level failure — timeout, connection refused, DNS failure."""

    def __init__(self, message: str = "Network error", **kwargs):
        super().__init__(message=message, status_code=None, **kwargs)


class RazorpayUnknownError(RazorpayClientError):
    """Unexpected status code or unclassified error."""

    def __init__(self, message: str = "Unknown error", **kwargs):
        super().__init__(message=message, **kwargs)
