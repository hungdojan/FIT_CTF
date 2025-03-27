class CTFException(Exception):
    """Base CTF exception class."""

    pass


class ProjectNamingFormatException(CTFException):
    """Given project name does not follow the allowed format."""

    pass


class UsernameFormatException(CTFException):
    """Given username does not follow the allowed format."""

    pass


class ProjectNotExistException(CTFException):
    """A project with the given name does not exist."""

    pass


class ProjectExistsException(CTFException):
    """A project with the given name already exists."""

    pass


class DirNotEmptyException(CTFException):
    """A directory with the given path does not exist."""

    pass


class DirNotExistsException(CTFException):
    """A directory with the given path already exists."""

    pass


class UserNotExistsException(CTFException):
    """A user with the given username does not exist."""

    pass


class UserExistsException(CTFException):
    """A user with the given username already exists."""

    pass


class SSHPortOutOfRangeException(CTFException):
    """A selected port is out of allowed range."""

    pass


class UserNotEnrolledToProjectException(CTFException):
    """A given user is not enrolled to the selected project."""

    pass


class UserEnrolledToProjectException(CTFException):
    """A given user is enrolled to the selected project."""

    pass


class MaxUserCountReachedException(CTFException):
    """A maximal number of users per project reached."""

    pass


class ContainerPortUsageCollisionException(CTFException):
    """A selected container port is already in use."""

    pass


class ForwardedPortUsageCollisionException(CTFException):
    """A selected forwarded port is already in use."""

    pass


class ModuleExistsException(CTFException):
    """A module with the given name already exists."""

    pass


class ModuleNotExistsException(CTFException):
    """A module with the given name does not exist."""

    pass


class DataFileNotExistException(CTFException):
    """A configuration file could not be located."""

    pass


class DataValidationErrorException(CTFException):
    """A provided file is not syntactically correct."""

    pass


class ShadowPathNotExistException(CTFException):
    """A shadow for of the selected user does not exist."""

    pass


class ValidatorNotExistException(CTFException):
    """A validator with given name does not exist."""

    pass


class SchemaFileNotExistException(CTFException):
    """A schema file could not be located."""

    pass


class ServiceNotExistException(CTFException):
    """The service with the given name does not exist."""

    pass


class ServiceExistException(CTFException):
    """The service with the given name already exist."""

    pass


class ConfigurationFileNotEditedException(CTFException):
    """The configuration data were not edited in the editor."""

    pass


class ImportFileCorruptedException(CTFException):
    """All the errors that occur during project import."""

    pass


class ModuleInUseException(CTFException):
    """The selected module is still used by some kind of server"""

    pass
