class WebError(Exception):
    """Base Exception for Web package"""


class ServerLookupError(WebError):
    """Exception Raised when no Server Found"""