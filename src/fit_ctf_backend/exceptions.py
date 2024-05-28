class CTFException(Exception):
    pass


class ProjectNotExistsException(CTFException):
    pass


class ProjectExistsException(CTFException):
    pass


class DirNotEmptyException(CTFException):
    pass


class DirNotExistsException(CTFException):
    pass


class UserNotExistsException(CTFException):
    pass


class UserExistsException(CTFException):
    pass


class SSHPortOutOfRangeException(CTFException):
    pass


class UserNotAssignedToProjectException(CTFException):
    pass


class MaxUserCountReachedException(CTFException):
    pass


class PortUsageCollisionException(CTFException):
    pass


class ModuleExistsException(CTFException):
    pass


class ModuleNotExistsException(CTFException):
    pass
