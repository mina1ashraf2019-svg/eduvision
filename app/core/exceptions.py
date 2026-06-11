class EduVisionError(Exception):
    """Base exception for all EduVision errors."""
    pass

class AuthError(EduVisionError):
    pass

class PermissionDenied(EduVisionError):
    pass

class NotFoundError(EduVisionError):
    pass

class ValidationError(EduVisionError):
    pass

class StorageError(EduVisionError):
    pass

class InvalidMimeTypeError(StorageError):
    pass

class AccessCodeError(EduVisionError):
    pass

class EnrollmentError(EduVisionError):
    pass

class DuplicateError(EduVisionError):
    pass
