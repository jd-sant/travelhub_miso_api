from datetime import datetime, timedelta, timezone
from hmac import compare_digest

from core.config import settings
from core.jwt_handler import create_token
from core.otp import hash_otp
from core.roles import UserRole
from domain.ports.audit_repository import AuditRepository
from domain.ports.login_attempt_repository import LoginAttemptRepository
from domain.ports.otp_repository import OtpRepository
from domain.ports.user_lock_repository import UserLockRepository
from domain.schemas.auth import OtpVerifyRequest, TokenResponse
from domain.use_cases.base import BaseUseCase
from errors import (
    AccountLockedError,
    InvalidOtpError,
    OtpExpiredError,
    OtpMaxAttemptsError,
)


class VerifyOtpUseCase(BaseUseCase[OtpVerifyRequest, TokenResponse]):
    def __init__(
        self,
        otp_repo: OtpRepository,
        login_attempt_repo: LoginAttemptRepository,
        audit_repo: AuditRepository,
        user_lock_repo: UserLockRepository,
    ):
        self.otp_repo = otp_repo
        self.login_attempt_repo = login_attempt_repo
        self.audit_repo = audit_repo
        self.user_lock_repo = user_lock_repo

    def execute(
        self, payload: OtpVerifyRequest, ip_address: str
    ) -> TokenResponse:
        now = datetime.now(timezone.utc)
        email = str(payload.email)

        lock = self.user_lock_repo.get_lock(email)
        if lock:
            locked_until = lock.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until > now:
                raise AccountLockedError()

        otp = self.otp_repo.get_active(email)
        if otp is None:
            raise OtpExpiredError()

        if not compare_digest(hash_otp(payload.otp_code), otp.code):
            attempts = self.otp_repo.increment_attempts(otp.id)

            if attempts >= settings.otp_max_attempts:
                locked_until = now + timedelta(
                    minutes=settings.account_lock_minutes
                )
                self.user_lock_repo.create_lock(email, locked_until)
                self.otp_repo.invalidate_all(email)
                self.audit_repo.record(
                    entity_type="auth",
                    action="account_locked",
                    ip_address=ip_address,
                    user_id=otp.user_id,
                )
                raise OtpMaxAttemptsError()

            self.audit_repo.record(
                entity_type="otp",
                action="otp_failed",
                ip_address=ip_address,
                user_id=otp.user_id,
            )
            raise InvalidOtpError()

        self.otp_repo.mark_used(otp.id)

        roles = [r for r in otp.roles.split(",") if r]
        role = roles[0] if roles else UserRole.get_default()

        token = create_token(
            user_id=otp.user_id, email=email, role=role
        )

        self.login_attempt_repo.record(
            ip_address=ip_address,
            success=True,
            user_id=otp.user_id,
        )
        self.audit_repo.record(
            entity_type="auth",
            action="login_success",
            ip_address=ip_address,
            user_id=otp.user_id,
        )

        return TokenResponse(access_token=token, role=role)
