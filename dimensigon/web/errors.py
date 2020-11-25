import json
import traceback
import typing as t
from datetime import datetime
from http.client import HTTPException

import flask
from flask import Blueprint, jsonify, current_app
from jsonschema import ValidationError
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import InternalServerError

from dimensigon import defaults
from dimensigon.utils.decorators import reify
from dimensigon.utils.helpers import is_iterable_not_string, is_string_types, format_exception
from dimensigon.utils.typos import Id

if t.TYPE_CHECKING:
    from dimensigon.web.network import Response
    from dimensigon.domain.entities import Scope, State, Server, Step
    from dimensigon.domain.entities.route import RouteContainer

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


def format_error_content(error, debug=False):
    content = {
        'error': {
            'type': error.__class__.__name__,
            'message': error.format()
        }
    }

    if error.payload:
        content['error'].update(error.payload)
    if debug:
        content['error'].update(traceback=format_exception(error))
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
                          'path': list(error.relative_schema_path)[:-1],
                          'schema': error.schema}}
    return response, 400


@bp_errors.app_errorhandler(HTTPException)
def handle_HTTP_exception(e):
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

    response = {'error': {}}

    if current_app.config['DEBUG']:
        tb = [call_string.splitlines() for call_string in traceback.format_tb(original.__traceback__)]
        tb = [val for sublist in tb for val in sublist]
        response['error'].update(type=original.__class__.__name__,
                                 message=str(original),
                                 traceback=tb)
    else:
        response['error'].update(type=error.__class__.__name__, message=error.description)
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


class UserForbiddenError(BaseError):
    status_code = 404

    def _format_error_msg(self) -> str:
        return "User has no rights to perform the action"


class AlreadyExists(BaseError):
    status_code = 404

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def _format_error_msg(self) -> str:
        return f"already exists in database"

    @property
    def payload(self) -> t.Optional[dict]:
        return {self.name: self.value}


class EntityAlreadyExists(BaseError):
    status_code = 404

    def __init__(self, entity: str, ident, columns: t.Iterable[str] = None):
        self.entity = entity
        self.id = ident
        if is_iterable_not_string(columns):
            self.columns = list(columns)
        elif is_string_types(columns):
            self.columns = [columns]
        else:
            self.columns = ['id']

    def _format_error_msg(self) -> str:
        return f"{self.entity} with given {', '.join(self.columns)} already exists"

    @property
    def payload(self) -> t.Optional[dict]:
        return dict(entity=self.entity, id=self.id)


class EntityNotFound(BaseError):
    status_code = 404

    def __init__(self, entity: str, ident, columns: t.List[str] = None):
        self.entity = entity
        self.id = ident
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
        return dict(entity=self.entity, id=self.id)


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


class ServerDeleteError(BaseError):
    status_code = 404

    def _format_error_msg(self) -> str:
        return f"Server to delete must not be de current server"


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


class NoServerToLock(LockerError):

    def _format_error_msg(self) -> str:
        return 'No server was found for locking'


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
            try:
                data = dict({'id': str(r.server.id), 'name': r.server.name})
            except Exception:
                data = dict()
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


class EmptyTarget(BaseError):
    status_code = 400

    def __init__(self, target: str):
        self.target = target

    def _format_error_msg(self) -> str:
        return f"Target does not have any host specified"


class DuplicatedId(BaseError):
    status_code = 400

    def __init__(self, rid):
        self.rid = rid

    def _format_error_msg(self) -> str:
        return "Id already exists"

    @property
    def payload(self) -> t.Optional[dict]:
        return {'id': self.rid}


class UndoStepWithoutParent(BaseError):

    def __init__(self, step_id: Id) -> None:
        self.step_id = step_id

    def _format_error_msg(self) -> str:
        return "'undo' step must have a parent step"


class ParentUndoError(BaseError):

    def __init__(self, step_id: Id, parent_step_ids: t.Union[Id, t.List[Id]]) -> None:
        if isinstance(parent_step_ids, str):
            self.parent_step_ids = [parent_step_ids]
        else:
            self.parent_step_ids = parent_step_ids
        self.step_id = step_id

    def _format_error_msg(self) -> str:
        return "a 'do' step cannot have parent 'undo' steps"


class ChildDoError(BaseError):

    def __init__(self, step_id: Id, child_step_ids: t.Union[Id, t.List[Id]]) -> None:
        if isinstance(child_step_ids, str):
            self.child_step_ids = [child_step_ids]
        else:
            self.child_step_ids = child_step_ids
        self.step_id = step_id

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


class MissingSourceMapping(BaseError):
    status_code = 404

    def __init__(self, parameter):
        self.parameter = parameter

    def _format_error_msg(self) -> str:
        return "Missing mapping parameter"


class MappingError(BaseError):
    status_code = 404

    def __init__(self, parameter, step: 'Step' = None, ):
        self.parameter = parameter
        if step:
            self.step = {'id': step.id}
            if step.name:
                self.step.update(name=step.name)
            self.orchestration = {'id': step.orchestration.id, 'name': step.orchestration.name,
                                  'version': step.orchestration.version}

    def _format_error_msg(self) -> str:
        return "Mapping source parameter not found in input"


class MissingParameters(BaseError):
    status_code = 404

    def __init__(self, parameters, step: 'Step' = None, server: 'Server' = None):
        self.parameters = parameters
        if step:
            self.step = {'id': step.id}
            if step.name:
                self.step.update(name=step.name)
            self.orchestration = {'id': step.orchestration.id, 'name': step.orchestration.name,
                                  'version': step.orchestration.version}
        if server:
            self.server = {'id': server.name, 'name': server.name}

    def _format_error_msg(self) -> str:
        if hasattr(self, 'server'):
            return "Missing parameters in step on runtime"
        else:
            return "Missing parameters in step"


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


class NoSoftwareServer(BaseError):
    status_code = 500

    def __init__(self, software_id):
        self.software_id = software_id

    def _format_error_msg(self) -> str:
        return "Software does not have any server location"


class ChunkSendError(BaseError):
    status_code = 500

    def __init__(self, chunk_responses: t.Dict[int, 'Response']):
        self.chunk_responses = chunk_responses

    def _format_error_msg(self) -> str:
        return "Error while trying to send chunks to server"

    @property
    def payload(self) -> t.Optional[dict]:
        return {'chunks': {c: r.to_dict() for c, r in self.chunk_responses.items()}}


class TransferBase(BaseError):
    status_code = 409


class TransferFileAlreadyExists(TransferBase):

    def __init__(self, file=None):
        self.file = file

    def _format_error_msg(self) -> str:
        return "File already exists. Use force=True if needed"


class TransferFileAlreadyOpen(TransferBase):

    def __init__(self, file=None):
        self.file = file

    def _format_error_msg(self) -> str:
        return "There is already a transfer sending file"


class TransferSoftwareAlreadyOpen(TransferBase):

    def __init__(self, software_id=None):
        self.software_id = software_id

    def _format_error_msg(self) -> str:
        return "There is already a transfer sending software"


class TransferNotInValidState(TransferBase):
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
        from dimensigon.domain.entities import Server
        try:
            p = proxy or Server.get_current()
        except NoResultFound:
            p = None

        self.destination = dict(name=server.name, id=server.id)
        self.proxy = dict(name=p.name, id=p.id) if p else None

    def _format_error_msg(self) -> str:
        return f"Unreachable destination"

    @property
    def payload(self) -> t.Optional[dict]:
        data = dict(destination=self.destination)
        if self.proxy:
            data.update(proxy=self.proxy)
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


class ParameterMustBeSet(BaseError):
    status_code = 404

    def __init__(self, msg):
        self.msg = msg

    def _format_error_msg(self) -> str:
        return self.msg


class InvalidRoute(BaseError):
    status_code = 500

    def __init__(self, destination: 'Server', rc: 'RouteContainer'):
        self.destination = destination
        self.rc = rc
        # to load data
        self.payload

    def _format_error_msg(self) -> str:
        return "trying to set an invalid Route"

    @reify
    def payload(self) -> t.Optional[dict]:
        data = {'route': {'destination': {'id': self.destination.id, 'name': self.destination.name},
                          'proxy_server': None, 'gate': None, 'cost': None}}
        if self.rc.proxy_server:
            data['route']['proxy_server'] = {'id': self.rc.proxy_server.id, 'name': self.rc.proxy_server.name}
        if self.rc.gate:
            data['route']['gate'] = {'id': self.rc.gate.id, 'gate': str(self.rc.gate)}
        if self.rc.cost is not None:
            data['route']['cost'] = self.rc.cost

        return data


class InvalidDateFormat(BaseError):
    status_code = 404

    def __init__(self, date: str, expected_format: str):
        self.input_date = date
        self.expected_format = expected_format

    def _format_error_msg(self) -> str:
        return "Date is not a valid format"


class InvalidValue(BaseError):
    status_code = 404

    def __init__(self, msg: str, **kwargs):
        self.msg = msg
        self.kwargs = kwargs

    def _format_error_msg(self) -> str:
        return self.msg

    @property
    def payload(self) -> t.Optional[dict]:
        return self.kwargs
