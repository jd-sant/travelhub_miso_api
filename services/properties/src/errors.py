class PropertyNotFoundError(Exception):
    """Exception raised when property is not found"""
    pass


class SeasonalPricingNotFoundError(Exception):
    """Exception raised when seasonal pricing is not found"""
    pass


class PricingSignatureVerificationError(Exception):
    """Exception raised when pricing signature verification fails"""
    pass


class PricingIntegrityLockedError(Exception):
    """Exception raised when an update is attempted on a locked pricing record"""
    pass


class PricingOwnershipError(Exception):
    """Exception raised when user doesn't own the property"""
    pass


class AuthenticationError(Exception):
    """Exception raised when admin authentication fails (invalid/expired token)"""
    pass
