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
    """Exception raised when pricing record is locked due to integrity failure"""
    pass


class PricingOwnershipError(Exception):
    """Exception raised when user doesn't own the property"""
    pass
