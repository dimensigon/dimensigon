from abc import ABC, abstractmethod

import jsonschema
from flask import Response, app


class AbstractError(ABC):
    http_error_code = 400

    @abstractmethod
    def _format_error_msg(self) -> dict:
        pass

    def format(self) -> str:
        return self._format_error_msg(), self.http_error_code


class GenericError(AbstractError):
    http_error_code = 400

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def _format_error_msg(self) -> dict:
        return {'error': f'Generic Error. {self.args}, {self.kwargs}'}


class UnknownServer(AbstractError):
    http_error_code = 400

    def __init__(self, server_id: str):
        self.server_id = server_id

    def _format_error_msg(self) -> dict:
        return {'error': f"Unknown Server '{self.server_id}'"}

#
# @app.errorhandler(jsonschema.ValidationError)
# def on_ValidationError(e):
#     return {"error": "There was a validation error: " + str(e)}, 400
