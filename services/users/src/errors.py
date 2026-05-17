class UserConflictError(Exception):
    pass


class InvalidUserRoleError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidTokenError(Exception):
    pass


class TokenExpiredError(Exception):
    pass


class PrivacySearchUnavailableError(Exception):
    pass
