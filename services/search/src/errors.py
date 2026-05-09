class InvalidSearchRuleError(Exception):
    pass


class PropertiesServiceUnavailableError(Exception):
    pass


class ReservationsServiceUnavailableError(Exception):
    pass


class PricingValidationError(Exception):
    pass


class PricingConflictError(Exception):
    pass


class PricingAuthorizationError(Exception):
    pass


class PricingTargetNotFoundError(Exception):
    pass
