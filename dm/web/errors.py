import json
import typing as t
from http.client import HTTPException

from flask import Blueprint, jsonify
from jsonschema import ValidationError
from werkzeug.exceptions import InternalServerError

from dm.utils.helpers import is_iterable_not_string, is_string_types

if t.TYPE_CHECKING:
    from dm.domain.entities import Scope, State, Server
    from dm.use_cases.lock import ResponseServer

bp_errors = Blueprint('errors', __name__)


class BaseError(Exception):
    status_code = 400

    def _format_error_msg(self) -> str:
        pass

    def format(self) -> str:
        return self._format_error_msg()

    @property
    def payload(self) -> t.Optional[dict]:
        return None

    def __str__(self):
        msg = self.format()
        return f"{msg}: {self.payload}"


def format_error_response(error):
    response = {
        'error': {
            'type': error.__class__.__name__,
            'message': error.format()
        }
    }

    if error.payload:
        response['error'].update(error.payload)

    rv = jsonify(response)
    rv.status_code = error.status_code or 500

    return rv


@bp_errors.app_errorhandler(BaseError)
def handle_error(error):
    return format_error_response(error)


@bp_errors.app_errorhandler(ValidationError)
def validation_error(error: ValidationError):
    response = {"error": {'type': error.__class__.__name__,
                          'message': error.message,
                          'schema': error.schema}}
    return response, 400


@bp_errors.app_errorhandler(HTTPException)
def handle_exception(e):
    """Return JSON instead of HTML for HTTP errors."""
    # start with the correct headers and status code from the error
    response = e.get_response()
    # replace the body with JSON
    response.data = json.dumps({'error': {'type': e.name, 'message': e.description}})
    response.content_type = "application/json"
    return response


@bp_errors.app_errorhandler(InternalServerError)
def handle_500(error):
    status_code = 500
    original = getattr(error, "original_exception", None)

    response = {'error': {
        'type': error.__class__.__name__,
        'message': error.description,
    }
    }

    # if current_app.config['DEBUG']:
    #
    #     args = [str(x) for x in error.args]
    #     if len(args) == 1:
    #         response['error']['message'] = args[0]
    #     elif len(args) > 1:
    #         response['error']['message'] = args

    return jsonify(response), status_code


class GenericError(BaseError):

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self._payload = payload

    def _format_error_msg(self):
        return self.message

    @property
    def payload(self) -> dict:
        return self._payload


class EntityNotFound(BaseError):
    status_code = 404

    def __init__(self, entity: str, ident, columns: t.List[str] = None):
        self.entity = entity
        self.ident = ident
        if is_iterable_not_string(columns):
            self.columns = columns
        elif is_string_types(columns):
            self.columns = [columns]
        else:
            self.columns = ['id']

    def _format_error_msg(self) -> str:
        return f"{self.entity} with given {', '.join(self.columns)} doesn't exist"

    @property
    def payload(self) -> t.Optional[dict]:
        return dict(entity=self.entity, id=self.ident)


class NoDataFound(BaseError):
    status_code = 404

    def __init__(self, entity):
        self.entity = entity

    def _format_error_msg(self) -> str:
        return f"No data found"

    @property
    def payload(self) -> t.Optional[dict]:
        return dict(entity=self.entity)


class UnknownServer(BaseError):
    status_code = 404

    def __init__(self, server_id: str):
        self.server_id = server_id

    def _format_error_msg(self) -> str:
        return f"Unknown Server '{self.server_id}'"


class ObsoleteCatalog(BaseError):
    status_code = 409

    def __init__(self, actual_catalog, obsolete_catalog):
        self.actual_catalog = actual_catalog
        self.obsolete_catalog = obsolete_catalog

    def _format_error_msg(self) -> str:
        return f"Catalog is not up to date"

    @property
    def payload(self) -> t.Optional[dict]:
        return {'current': self.actual_catalog, 'old': self.obsolete_catalog}


class CatalogMismatch(BaseError):
    status_code = 500

    def __init__(self, local_entities, remote_entities):
        self.local_entities = local_entities
        self.remote_entities = remote_entities

    def _format_error_msg(self) -> str:
        return "List entities do not match"

    @property
    def payload(self) -> t.Optional[dict]:
        return dict(local_entities=self.local_entities, remote_entities=self.remote_entities)


#################
# Locker Errors #
#################

class LockerError(BaseError):
    status_code = 409
    action_map = {'L': 'lock', 'U': 'unlock', 'P': 'prevent'}

    def __init__(self, scope):
        self.scope = scope

    @property
    def payload(self) -> t.Optional[dict]:
        return {'scope': self.scope.name}


class PriorityLocker(LockerError):
    def _format_error_msg(self) -> str:
        return 'Priority locker acquired'


class ApplicantLockerError(LockerError):
    def _format_error_msg(self) -> str:
        return f'Another applicant has the scope acquired'


class StatusLockerError(LockerError):

    def __init__(self, scope: 'Scope', action: str, current_state: 'State'):
        super().__init__(scope)
        self.action = self.action_map.get(action, action)
        self.current_state = current_state

    def _format_error_msg(self) -> str:
        return f"Unable to perform locker state transition"

    @property
    def payload(self) -> t.Optional[dict]:
        p = super().payload
        p.update(action=self.action, state=self.current_state.name)
        return p


class LockError(LockerError):

    def __init__(self, scope: 'Scope', action: str, responses: t.List['ResponseServer']):
        self.scope = scope
        self.action = self.action_map.get(action, action)
        self.responses = responses

    def _format_error_msg(self) -> str:
        return f"Unable to {self.action} on scope {self.scope.name}"

    @property
    def payload(self) -> t.Optional[dict]:
        return {'servers': [{'id': str(e.server.id), 'name': e.server.name, 'response': e.msg, 'code': e.code,
                             'exception': str(e.exception)} for e in
                            self.responses]}

    @property
    def status_code(self):
        codes = set([r.code for r in self.responses])
        if len(codes) == 1:
            return codes.pop()
        else:
            if any(map(lambda x: x.code is None or x.code >= 500, list(codes))):
                return 500
            else:
                return super().status_code


#################
# Common Errors #
#################
class UnreachableDestination(BaseError):
    status_code = 503

    def __init__(self, server: 'Server'):
        self.server = server

    def _format_error_msg(self) -> str:
        return f"Unreachable destination"

    def payload(self) -> t.Optional[dict]:
        return dict(server=dict(name=self.server.name, id=str(self.server.id)))


class KeywordReserved(BaseError):
    status_code = 400

    def __init__(self, msg):
        self.msg = msg

    def _format_error_msg(self) -> str:
        return self.msg
