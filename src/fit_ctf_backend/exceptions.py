class CTFException(Exception):
    """Base CTF exception class."""

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


class MaxUserCountReachedException(CTFException):
    """A maximal number of users per project reached."""

    pass


class PortUsageCollisionException(CTFException):
    """A selected port is already in use."""

    pass


class ModuleExistsException(CTFException):
    """A module with the given name already exists."""

    pass


class ModuleNotExistsException(CTFException):
    """A module with the given name does not exist."""

    pass
