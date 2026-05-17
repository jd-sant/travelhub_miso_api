from datetime import datetime, timedelta, timezone

from core.config import settings
from core.otp import generate_otp, hash_otp
from domain.ports.auth_repository import AuthRepository
from domain.ports.audit_repository import AuditRepository
from domain.ports.login_attempt_repository import LoginAttemptRepository
from domain.ports.otp_repository import OtpRepository
from domain.ports.otp_sender import OtpSender
from domain.ports.user_lock_repository import UserLockRepository
from domain.schemas.auth import LoginRequest, LoginResponse
from domain.use_cases.base import BaseUseCase
from errors import AccountLockedError, InvalidCredentialsError, IpBlockedError


class LoginUseCase(BaseUseCase[LoginRequest, LoginResponse]):
    def __init__(
        self,
        auth_repo: AuthRepository,
        otp_repo: OtpRepository,
        login_attempt_repo: LoginAttemptRepository,
        audit_repo: AuditRepository,
        user_lock_repo: UserLockRepository,
        otp_sender: OtpSender,
    ):
        self.auth_repo = auth_repo
        self.otp_repo = otp_repo
        self.login_attempt_repo = login_attempt_repo
        self.audit_repo = audit_repo
        self.user_lock_repo = user_lock_repo
        self.otp_sender = otp_sender

    def execute(self, payload: LoginRequest, ip_address: str) -> LoginResponse:
        now = datetime.now(timezone.utc)

        window_start = now - timedelta(
            minutes=settings.ip_block_window_minutes
        )
        failed_count = self.login_attempt_repo.count_failed_by_ip(
            ip_address, window_start
        )
        if failed_count >= settings.ip_block_threshold:
            self.audit_repo.record(
                entity_type="ip_block",
                action="ip_blocked",
                ip_address=ip_address,
            )
            raise IpBlockedError()

        lock = self.user_lock_repo.get_lock(str(payload.email))
        if lock:
            locked_until = lock.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until > now:
                raise AccountLockedError()
            self.user_lock_repo.delete_lock(str(payload.email))

        user = self.auth_repo.verify_credentials(
            str(payload.email), payload.password
        )
        if user is None:
            self.login_attempt_repo.record(
                ip_address=ip_address,
                success=False,
                failure_reason="invalid_credentials",
            )
            self.audit_repo.record(
                entity_type="auth",
                action="login_failed",
                ip_address=ip_address,
            )
            raise InvalidCredentialsError()

        self.otp_repo.invalidate_all(str(payload.email))

        code = generate_otp()
        hashed_code = hash_otp(code)
        expires_at = now + timedelta(minutes=settings.otp_expiry_minutes)
        self.otp_repo.create(
            user_id=user.id,
            email=str(payload.email),
            code=hashed_code,
            expires_at=expires_at,
            roles=user.roles,
        )

        self.otp_sender.send(str(payload.email), code)

        self.audit_repo.record(
            entity_type="otp",
            action="otp_sent",
            ip_address=ip_address,
            user_id=user.id,
        )

        return LoginResponse(message="OTP enviado al correo registrado")
