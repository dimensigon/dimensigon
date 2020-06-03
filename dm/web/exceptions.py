from flask import jsonify


def handle_web_errors(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


class WebError(Exception):
    """Base Exception for Web package"""


class ServerLookupError(WebError):
    """Exception Raised when no Server Found"""


class HTTPError(Exception):
    """Exception Raised when server returned a 400 or 500 message """
