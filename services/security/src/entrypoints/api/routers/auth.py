from fastapi import APIRouter, Depends, HTTPException, Request, status

from assembly import (
    get_login_use_case,
    get_validate_token_use_case,
    get_verify_otp_use_case,
)
from domain.schemas.auth import (
    LoginRequest,
    LoginResponse,
    OtpVerifyRequest,
    TokenResponse,
    TokenValidationRequest,
    TokenValidationResponse,
)
from domain.use_cases.login import LoginUseCase
from domain.use_cases.validate_token import ValidateTokenUseCase
from domain.use_cases.verify_otp import VerifyOtpUseCase
from errors import (
    AccountLockedError,
    InvalidCredentialsError,
    InvalidOtpError,
    InvalidTokenError,
    IpBlockedError,
    OtpExpiredError,
    OtpMaxAttemptsError,
    ServiceUnavailableError,
    TokenExpiredError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    payload: LoginRequest,
    request: Request,
    use_case: LoginUseCase = Depends(get_login_use_case),
) -> LoginResponse:
    ip = _get_client_ip(request)
    try:
        return use_case.execute(payload, ip_address=ip)
    except IpBlockedError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="IP bloqueada por múltiples intentos fallidos",
        )
    except AccountLockedError:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Cuenta bloqueada temporalmente",
        )
    except ServiceUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio no disponible, intente más tarde",
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )


@router.post(
    "/verify-otp",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def verify_otp(
    payload: OtpVerifyRequest,
    request: Request,
    use_case: VerifyOtpUseCase = Depends(get_verify_otp_use_case),
) -> TokenResponse:
    ip = _get_client_ip(request)
    try:
        return use_case.execute(payload, ip_address=ip)
    except AccountLockedError:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Cuenta bloqueada temporalmente",
        )
    except OtpExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OTP expirado",
        )
    except OtpMaxAttemptsError:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Cuenta bloqueada por múltiples intentos fallidos de OTP",
        )
    except InvalidOtpError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código OTP inválido",
        )


@router.post(
    "/validate-token",
    response_model=TokenValidationResponse,
    status_code=status.HTTP_200_OK,
)
def validate_token(
    payload: TokenValidationRequest,
    use_case: ValidateTokenUseCase = Depends(get_validate_token_use_case),
) -> TokenValidationResponse:
    try:
        return use_case.execute(payload)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )
