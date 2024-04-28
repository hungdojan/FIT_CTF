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


class SSHPortOutOfRangeException(CTFException):
    pass


class UserNotAssignedToProjectException(CTFException):
    pass
