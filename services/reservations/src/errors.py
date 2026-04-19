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


class ReservationPreviewValidationError(Exception):
    pass


class PropertyNotFoundError(Exception):
    pass


class PropertyServiceUnavailableError(Exception):
    pass
