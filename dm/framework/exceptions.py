class FrameworkError(Exception):
    """Base Class Exception"""


class QueryError(FrameworkError):
    """Base Class for Query Errors"""


class NoSchemaDefined(QueryError):
    """Raised when no schema is defined in the repository"""


class NotFound(QueryError):
    """The object trying to be found does not exist"""


class NoResultFound(QueryError):
    """No object is found for the related predicate"""


class MultipleResultsFound(QueryError):
    """Multple result where found for """


class ConflictQueryArguments(QueryError):
    """Conflict with arguments from query"""


class UnrestrictedRemove(QueryError):
    """
    A trivial query has been found while doing remove. If you want to clear all the entries in the dao,
    use `clear` explicitly.
    """


class EntityNotYetAdded(QueryError):
    """An operation was tried to be made on an entity, that hasn't been added to the repository "
        "yet and thus is invalid."""


class IdAlreadyExists(QueryError):
    """An insertion of an object with an ID already into the register"""


class DuplicatedEntities(QueryError):
    """more than one entity with the same ID registered into the register"""


class DIError(Exception):
    """Base Class for Dependency Injection Errors"""


class DefinitionNotFound(DIError):
    """A dependency definition for DI was tried to be injected, but it has not been found."""


class AmbiguousDefinition(DIError):
    """This identifier has already been registered."""


class NoIdentifierSpecified(DIError):
    """Missing both name and interface for Inject."""


class NoContainerProvided(DIError):
    """DI resolving found no instance of the DI `Container` to work with."""


class GlobalContainerNotSet(NoContainerProvided):
    """DI resolving found no instance of the DI `Container` to work with."""


class IntegrationNotFound(DIError):
    """An integration target tried to use its external library, but it has not been found."""
