"""Exception classes for BYD China API client."""


class BydError(Exception):
    """Base exception for BYD API errors."""


class BydAuthenticationError(BydError):
    """Authentication failed (invalid credentials)."""

    def __init__(self, message: str = "", code: str = "", endpoint: str = ""):
        super().__init__(message)
        self.code = code
        self.endpoint = endpoint


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


class BydCryptoError(BydError):
    """Cryptographic operation failed (AES encrypt/decrypt)."""


class BydDecryptionError(BydError):
    """Decryption failed (WBSK or AES)."""


class BydEndpointNotSupportedError(BydError):
    """The requested endpoint/command is not supported for this vehicle."""

    def __init__(self, message: str = "", code: str = "", endpoint: str = ""):
        super().__init__(message)
        self.code = code
        self.endpoint = endpoint


class BydRemoteControlError(BydError):
    """Remote control command was rejected by the cloud."""

    def __init__(self, message: str = "", code: str = "", endpoint: str = ""):
        super().__init__(message)
        self.code = code
        self.endpoint = endpoint


class BydSessionExpiredError(BydError):
    """Session/token has expired and needs re-authentication."""

    def __init__(self, message: str = "", code: str = "", endpoint: str = ""):
        super().__init__(message)
        self.code = code
        self.endpoint = endpoint


class BydRateLimitError(BydError):
    """API rate limit exceeded."""

    def __init__(self, message: str = "", code: str = "", endpoint: str = ""):
        super().__init__(message)
        self.code = code
        self.endpoint = endpoint


class BydDataUnavailableError(BydError):
    """Requested data is not available at this time."""


class BangcleError(BydError):
    """Bangcle/WBSK protection error."""


class BangcleTableLoadError(BangcleError):
    """Bangcle protection table could not be loaded."""
