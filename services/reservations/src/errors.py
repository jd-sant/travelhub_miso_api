class ReservationNotFoundError(Exception):
    pass


class ReservationConflictError(Exception):
    pass


class RoomNotAvailableError(Exception):
    pass


class InvalidReservationDateError(Exception):
    pass
