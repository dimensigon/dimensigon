import typing as t

from dm.utils.typos import UUID

"""
Exceptions for Use Case errors
IDs from 1000 to 1999
"""


# Interactor Exceptions
class UseCaseException(Exception):
    """Base Class for Use Cases Exceptions"""
    _id = 1000


class ServersMustNotBeBlank(UseCaseException):
    _id = 1001


class ErrorServerLock(UseCaseException):
    _id = 1002

    def __init__(self, server: UUID, msg, code, *args):
        self.server = server
        self.code = code
        self.msg = msg

        super().__init__(*args)

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
               and self.server == other.server \
               and self.code == other.code \
               and self.msg == other.msg \
               and self.args == other.args


class UpgradeCatalog(UseCaseException):
    """Error while trying to upgrade the catalog"""


class CatalogMismatch(UpgradeCatalog):
    """The Repos from remote do not correspond with the current repos"""


class ErrorLock(UseCaseException):
    _id = 1003

    def __init__(self, scope, errors: t.List[ErrorServerLock]):
        self.scope = scope
        self.errors = errors

    def __iter__(self) -> 'ErrorLock':
        self.n = -1
        return self

    def __next__(self):
        self.n += 1
        if self.n < len(self.errors):
            return self.errors[self.n]
        raise StopIteration

    def to_json(self):
        d = {'error': self.__class__.__name__}
        d.update(servers=[])
        for e in self:
            if e.server.id:
                d['servers'].append(dict(server_id=str(e.server.id), code=e.code,
                                         response=e.msg if isinstance(e.msg, dict) else str(e.msg)))
            else:
                d['servers'].append(
                    dict(server=str(e.server), code=e.code, response=e.msg if isinstance(e.msg, dict) else str(e.msg)))
        return d

    def __str__(self):
        return '\n'.join([f"Server {e.server}: {e.code}, {e.msg}" for e in self])


class ErrorUnLock(ErrorLock):
    ...


class ErrorPreventingLock(ErrorLock):
    ...


class MediatorError(Exception):
    """Error related with Class Mediator"""


class CommunicationError(MediatorError):
    """An error occurred while trying to communicate with a server"""


class TransferTimeout(UseCaseException):
    """A timeout while waiting for transfer to end"""


class TransferError(UseCaseException):
    """Error ocurred when trying to send chunks"""
