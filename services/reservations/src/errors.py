class ReservationNotFoundError(Exception):
    pass


class ReservationConflictError(Exception):
    pass


class RoomNotAvailableError(Exception):
    pass


class InvalidReservationDateError(Exception):
    pass


class ReservationSchedulingError(Exception):
    pass


class InvalidReservationStatusError(Exception):
    pass


class ReservationStateConflictError(Exception):
    pass


class ReservationAuthorizationError(Exception):
    pass


class TokenExpiredError(Exception):
    pass


class InvalidTokenError(Exception):
    pass
