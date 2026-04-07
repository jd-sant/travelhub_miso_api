from functools import wraps
from typing import Callable

from fastapi import HTTPException, Request, status


def require_role(required_role: str) -> Callable:
    """
    Decorador que valida que el usuario tenga un rol específico.
    
    Retorna 401 Unauthorized si no hay usuario autenticado.
    Retorna 403 Forbidden si el usuario no tiene el rol requerido.
    
    Uso:
        @router.get("/users")
        @require_role("admin")
        def get_users(request: Request):
            ...
    
    Args:
        required_role: El rol requerido (ej: "admin", "hotel", "traveler")
    
    Raises:
        HTTPException 401: Si no hay usuario autenticado
        HTTPException 403: Si el usuario no tiene el rol requerido
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Busca el parámetro Request en los argumentos o kwargs
            request: Request = None
            
            # Busca en kwargs
            if "request" in kwargs:
                request = kwargs["request"]
            else:
                # Busca en args (usualmente el primer argumento)
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No request object found",
                )
            
            # Obtiene el usuario del middleware
            user = getattr(request.state, "user", None)
            
            # Si no hay usuario, retorna 401
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No autorizado",
                )
            
            # Si el usuario no tiene el rol requerido, retorna 403
            if user.get("role") != required_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Se requiere rol '{required_role}'",
                )
            
            # Continúa con la función original
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Busca el parámetro Request en los argumentos o kwargs
            request: Request = None
            
            # Busca en kwargs
            if "request" in kwargs:
                request = kwargs["request"]
            else:
                # Busca en args (usualmente el primer argumento)
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No request object found",
                )
            
            # Obtiene el usuario del middleware
            user = getattr(request.state, "user", None)
            
            # Si no hay usuario, retorna 401
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No autorizado",
                )
            
            # Si el usuario no tiene el rol requerido, retorna 403
            if user.get("role") != required_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Se requiere rol '{required_role}'",
                )
            
            # Continúa con la función original
            return func(*args, **kwargs)
        
        # Retorna el wrapper apropiado (async o sync)
        if hasattr(func, "__code__") and func.__code__.co_flags & 0x100:
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
