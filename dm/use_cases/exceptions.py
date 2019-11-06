import typing as t

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

    def __init__(self, server, msg, *args):
        self.server = server
        super().__init__(msg, *args)


class UpgradeCatalog(UseCaseException):
    """Error while trying to upgrade the catalog"""


class CatalogMismatch(UpgradeCatalog):
    """The Repos from remote do not correspond with the current repos"""


class ErrorLock(UseCaseException):
    _id = 1003

    def __init__(self, errors: t.List[ErrorServerLock]):
        self.errors = errors

    def __iter__(self) -> 'ErrorLock':
        self.n = -1
        return self

    def __next__(self):
        self.n += 1
        if self.n < len(self.errors):
            return self.errors[self.n]
        raise StopIteration


class MediatorError(Exception):
    """Error related with Class Mediator"""


class CommunicationError(MediatorError):
    """An error occurred while trying to communicate with a server"""
