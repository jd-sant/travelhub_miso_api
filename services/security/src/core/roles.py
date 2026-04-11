class UserRole:
    """Definición de los 3 roles del sistema"""
    TRAVELER = "traveler"
    HOTEL = "hotel"
    ADMIN = "admin"
    
    ALL = [TRAVELER, HOTEL, ADMIN]
    
    @staticmethod
    def is_valid(role: str) -> bool:
        """Valida si un rol es válido"""
        return role in UserRole.ALL
    
    @staticmethod
    def get_default() -> str:
        """Retorna el rol por defecto para nuevos usuarios"""
        return UserRole.TRAVELER
