"""
Exceptions for Domain Errors
IDs from 2000 to 2099
"""


class GatewayError(Exception):
    """Base Class for Gateway Exceptions"""


class TimeoutError(GatewayError):
    """Timeout reached while trying to execute the process"""


class UnknownMessageType(GatewayError):
    """an unknown message type was received"""


class UnknownFunctionMediator(GatewayError):
    """an unknown function was tried to be executed"""