import json
import typing as t
from datetime import datetime
from http.client import HTTPException

import flask
from flask import Blueprint, jsonify
from jsonschema import ValidationError
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import InternalServerError

from dm import defaults
from dm.utils.helpers import is_iterable_not_string, is_string_types

if t.TYPE_CHECKING:
    from dm.web.network import Response
    from dm.domain.entities import Scope, State, Server

bp_errors = Blueprint('errors', __name__)


class BaseError(Exception):
    status_code = 400

    def _format_error_msg(self) -> str:
        pass

    def format(self) -> str:
        return self._format_error_msg()

    @property
    def payload(self) -> t.Optional[dict]:
        return self.__dict__

    def __str__(self):
        msg = self.format()
        payload = None
        if self.payload:
            try:
                payload = json.dumps(self.payload, indent=4)
            except:
                try:
                    payload = str(self.__dict__)
                except:
                    pass
        if msg and payload:
            return f"{msg}\n{payload}"
        else:
            return msg if msg else payload


def format_error_content(error):
    content = {
        'error': {
            'type': error.__class__.__name__,
            'message': error.format()
        }
    }

    if error.payload:
        content['error'].update(error.payload)
    return content


def format_error_response(error) -> flask.Response:
    content = format_error_content(error)
    rv = jsonify(content)
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

    def __init__(self, message, status_code=None, **payload):
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


class ServerNormalizationError(BaseError):
    status_code = 404

    def __init__(self, idents: t.List[str]):
        self.idents = idents

    def _format_error_msg(self) -> str:
        return f"Servers not found in catalog: {', '.join(self.idents)}"


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


class UnknownServer(BaseError):
    status_code = 404

    def __init__(self, server_id: str):
        self.server_id = server_id

    def _format_error_msg(self) -> str:
        return f"Unknown Server '{self.server_id}'"


class ObsoleteCatalog(BaseError):
    status_code = 409

    def __init__(self, actual_catalog: datetime, obsolete_catalog: datetime):
        self.actual_catalog = actual_catalog
        self.obsolete_catalog = obsolete_catalog

    def _format_error_msg(self) -> str:
        return f"Catalog is not up to date"

    @property
    def payload(self) -> t.Optional[dict]:
        return {'current': self.actual_catalog.strftime(defaults.DATEMARK_FORMAT),
                'old': self.obsolete_catalog.strftime(defaults.DATEMARK_FORMAT)}


class CatalogMismatch(BaseError):
    status_code = 500

    def __init__(self, local_entities, remote_entities):
        self.local_entities = local_entities
        self.remote_entities = remote_entities

    def _format_error_msg(self) -> str:
        return "List entities do not match"

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

    def __init__(self, scope: 'Scope', action: str, responses: t.List['Response']):
        self.scope = scope
        self.action = self.action_map.get(action, action)
        self.responses = responses

    def _format_error_msg(self) -> str:
        return f"Unable to {self.action} on scope {self.scope.name}"

    @property
    def payload(self) -> t.Optional[dict]:
        responses = []
        for r in self.responses:
            data = dict({'id': str(r.server.id), 'name': r.server.name})
            if r.code:
                data.update(response=r.msg, code=r.code)
            else:
                if isinstance(r.exception, BaseError):
                    data.update(format_error_content(r.exception))
                else:
                    data.update(error=str(r.exception) if str(r.exception) else r.exception.__class__.__name__)
            responses.append(data)
        return {'servers': responses}

    @property
    def status_code(self):
        codes = set([r.code for r in self.responses])
        if len(codes) == 1:
            return codes.pop()
        else:
            if any(map(lambda c: c is None or c >= 500, list(codes))):
                return 500
            else:
                return super().status_code


########################
# Orchestration Errors #
########################
class TargetUnspecified(BaseError):
    status_code = 404

    def __init__(self, target: t.Iterable[str]):
        self.target = list(target)

    def _format_error_msg(self) -> str:
        return f"Target not specified"


class TargetNotNeeded(BaseError):
    status_code = 400

    def __init__(self, target: t.Iterable[str]):
        self.target = list(target)

    def _format_error_msg(self) -> str:
        return f"Target not in orchestration"


class DuplicatedId(BaseError):
    status_code = 400

    def __init__(self, rid):
        self.rid = rid

    def _format_error_msg(self) -> str:
        return "Id already exists"

    @property
    def payload(self) -> t.Optional[dict]:
        return {'id': self.rid}

class ParentUndoError(BaseError):

    def _format_error_msg(self) -> str:
        return "fa 'do' step cannot have parent 'undo' steps"

class ChildDoError(BaseError):

    def _format_error_msg(self) -> str:
        return "an 'undo' step cannot have child 'do' steps"

class CycleError(BaseError):

    def _format_error_msg(self) -> str:
        return "Cycle detected while trying to add dependency"

##############
# Deployment #
##############

class Timeout(BaseError):
    status_code = 500

class RemoteServerTimeout(BaseError):
    status_code = 500

    def __init__(self, timeout, server, command):
        self.timeout = timeout
        self.server = server
        self.command = command

    def _format_error_msg(self) -> str:
        return "Timeout reached waiting remote server operation completion"


#############
# Send File #
#############

class SoftwareServerNotFound(BaseError):
    status_code = 404

    def __init__(self, software_id, server_id):
        self.software_id = software_id
        self.server_id = server_id

    def _format_error_msg(self) -> str:
        return "Software Server Association not found"


class ChunkSendError(BaseError):
    status_code = 500

    def __init__(self, chunk_responses: t.Dict[int, 'Response']):
        self.chunk_responses = chunk_responses

    def _format_error_msg(self) -> str:
        return "Error while trying to send chunks to server"

    @property
    def payload(self) -> t.Optional[dict]:
        return {'chunks': {c: r.to_dict() for c, r in self.chunk_responses.items()}}


class TransferNotInValidState(BaseError):
    status_code = 410

    def __init__(self, transfer_id: str, status: str):
        self.status = status
        self.transfer_id = transfer_id

    def _format_error_msg(self) -> str:
        return "Transfer not in a valid state"


#################
# Common Errors #
#################
class UnreachableDestination(BaseError):
    status_code = 503

    def __init__(self, server: 'Server', proxy: 'Server' = None):
        from dm.domain.entities import Server
        try:
            self.proxy = proxy or Server.get_current()
        except NoResultFound:
            self.proxy = None

        self.server = server

    def _format_error_msg(self) -> str:
        return f"Unreachable destination"

    @property
    def payload(self) -> t.Optional[dict]:
        data = dict(destination=dict(name=self.server.name, id=str(self.server.id)))
        if self.proxy:
            data.update(proxy=dict(name=self.proxy.name, id=str(self.proxy.id)))
        return data


class KeywordReserved(BaseError):
    status_code = 400

    def __init__(self, msg):
        self.msg = msg

    def _format_error_msg(self) -> str:
        return self.msg


class FileNotFound(BaseError):
    status_code = 404

    def __init__(self, file):
        self.file = file

    def _format_error_msg(self) -> str:
        return "File not found"


class HTTPError(BaseError):

    def __init__(self, resp: 'Response'):
        self.resp = resp
        self.status_code = resp.code if resp.code else 500

    def _format_error_msg(self) -> str:
        return "Error on request"

    @property
    def payload(self) -> t.Optional[dict]:
        return self.resp.to_dict()


class ProxyForwardingError(BaseError):
    status_code = 502

    def __init__(self, dest, exception):
        self.dest = dest
        self.exception = exception

    def _format_error_msg(self) -> str:
        return "Error while trying to forward request"

    @property
    def payload(self) -> t.Optional[dict]:
        return {'server': {'id': str(self.dest.id), 'name': self.dest.name},
                'exception': str(self.exception) if str(self.exception) else self.exception.__class__.__name__}


class HealthCheckMismatch(BaseError):
    status_code = 500

    def __init__(self, expected: t.Dict[str, str], actual: t.Dict[str, str]):
        self.expected = expected
        self.actual = actual

    def _format_error_msg(self) -> str:
        return "Healtcheck response does not match with the server requested"
