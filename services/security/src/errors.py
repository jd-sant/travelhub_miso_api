class InvalidCredentialsError(Exception):
    pass


class AccountLockedError(Exception):
    pass


class IpBlockedError(Exception):
    pass


class InvalidOtpError(Exception):
    pass


class OtpExpiredError(Exception):
    pass


class OtpMaxAttemptsError(Exception):
    pass


class TokenExpiredError(Exception):
    pass


class InvalidTokenError(Exception):
    pass


class ServiceUnavailableError(Exception):
    pass
