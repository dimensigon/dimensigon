"""
Exceptions for Domain Errors
IDs from 100 to 999
"""


class DomainException(Exception):
    """
    Base Class exception
    """
    _id = 100


class InjectionError(DomainException):
    """
    Exception raised when trying to add an id to Step that already exists
    """
    _id = 102


class CycleError(DomainException):
    """
    Exception raised when trying to add a node dependency which makes a cycle in the orchestration
    """
    _id = 103


# Locker Exceptions
class LockerError(DomainException):
    """Base Exception Class for Locker module"""
    _id = 104
    pass


class StateError(LockerError):
    """Exception for incorrect states"""
    _id = 105


class StateAlreadyInLock(StateError):
    """State already in LOCKED state"""
    _id = 106


class StateAlreadyInPreventingLock(StateError):
    """State already in PREVENTING LOCK state"""
    _id = 107


class StateAlreadyInUnlock(StateError):
    """State already in UNLOCK state"""
    _id = 108


class StateTransitionError(StateError):
    """State must be in PREVENTING LOCK to change to LOCK"""
    _id = 109

    def __init__(self, before, after):
        self.before = before
        self.after = after


class ApplicantError(LockerError):
    """Another applicant has the locker"""
    _id = 110


class PriorityError(LockerError):
    """A locker with higher priority is locked or trying to lock"""
    _id = 111


class CatalogError(DomainException):
    """
    Error raised when repository functions not set
    """
    _id = 120


class DataMarkError(CatalogError):
    """
    Error raised when past data mark generated
    """
    _id = 121


class NoDataMarkSet(CatalogError):
    """
    Error raised when catalog bypassed but no datemark passed into entity
    """
    _id = 122
