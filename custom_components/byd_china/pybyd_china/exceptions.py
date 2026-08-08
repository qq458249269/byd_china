"""Exception classes for BYD China API client."""


class BydError(Exception):
    """Base exception for BYD API errors."""


class BydAuthenticationError(BydError):
    """Authentication failed (invalid credentials)."""

    def __init__(self, message: str = "", code: str = "", endpoint: str = ""):
        super().__init__(message)
        self.code = code
        self.endpoint = endpoint


class BydSessionExpiredError(BydAuthenticationError):
    """Session/token expired or invalidated (code 22 — account logged in elsewhere).

    Callers should re-login and retry once with a fresh token envelope.
    """


class BydControlPasswordError(BydError):
    """Control PIN verification failed."""


class BydApiError(BydError):
    """API returned an error response."""

    def __init__(self, message: str = "", code: str = "", endpoint: str = ""):
        super().__init__(message)
        self.code = code
        self.endpoint = endpoint


class BydTransportError(BydError):
    """Network/transport error."""


class BydDecryptionError(BydError):
    """Decryption failed (WBSK or AES)."""
