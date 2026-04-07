from fastapi import Depends
from sqlmodel import Session

from adapters.repositories.audit_repository import SQLModelAuditRepository
from adapters.repositories.login_attempt_repository import (
    SQLModelLoginAttemptRepository,
)
from adapters.repositories.otp_repository import SQLModelOtpRepository
from adapters.repositories.user_lock_repository import (
    SQLModelUserLockRepository,
)
from adapters.services.log_otp_sender import LogOtpSender
from adapters.services.users_client import UsersServiceClient
from core.config import settings
from db.session import get_session
from domain.ports.audit_repository import AuditRepository
from domain.ports.auth_repository import AuthRepository
from domain.ports.login_attempt_repository import LoginAttemptRepository
from domain.ports.otp_repository import OtpRepository
from domain.ports.otp_sender import OtpSender
from domain.ports.user_lock_repository import UserLockRepository
from domain.use_cases.login import LoginUseCase
from domain.use_cases.validate_token import ValidateTokenUseCase
from domain.use_cases.verify_otp import VerifyOtpUseCase


def get_auth_repository() -> AuthRepository:
    return UsersServiceClient()


def get_otp_repository(
    session: Session = Depends(get_session),
) -> OtpRepository:
    return SQLModelOtpRepository(session)


def get_login_attempt_repository(
    session: Session = Depends(get_session),
) -> LoginAttemptRepository:
    return SQLModelLoginAttemptRepository(session)


def get_audit_repository(
    session: Session = Depends(get_session),
) -> AuditRepository:
    return SQLModelAuditRepository(session)


def get_user_lock_repository(
    session: Session = Depends(get_session),
) -> UserLockRepository:
    return SQLModelUserLockRepository(session)


def get_otp_sender() -> OtpSender:
    if settings.smtp_host:
        from adapters.services.smtp_otp_sender import SmtpOtpSender

        return SmtpOtpSender()
    return LogOtpSender()


def get_login_use_case(
    auth_repo: AuthRepository = Depends(get_auth_repository),
    otp_repo: OtpRepository = Depends(get_otp_repository),
    login_attempt_repo: LoginAttemptRepository = Depends(
        get_login_attempt_repository
    ),
    audit_repo: AuditRepository = Depends(get_audit_repository),
    user_lock_repo: UserLockRepository = Depends(get_user_lock_repository),
    otp_sender: OtpSender = Depends(get_otp_sender),
) -> LoginUseCase:
    return LoginUseCase(
        auth_repo=auth_repo,
        otp_repo=otp_repo,
        login_attempt_repo=login_attempt_repo,
        audit_repo=audit_repo,
        user_lock_repo=user_lock_repo,
        otp_sender=otp_sender,
    )


def get_verify_otp_use_case(
    otp_repo: OtpRepository = Depends(get_otp_repository),
    login_attempt_repo: LoginAttemptRepository = Depends(
        get_login_attempt_repository
    ),
    audit_repo: AuditRepository = Depends(get_audit_repository),
    user_lock_repo: UserLockRepository = Depends(get_user_lock_repository),
) -> VerifyOtpUseCase:
    return VerifyOtpUseCase(
        otp_repo=otp_repo,
        login_attempt_repo=login_attempt_repo,
        audit_repo=audit_repo,
        user_lock_repo=user_lock_repo,
    )


def get_validate_token_use_case() -> ValidateTokenUseCase:
    return ValidateTokenUseCase()
