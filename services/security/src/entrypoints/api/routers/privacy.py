from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from assembly import get_privacy_audit_repository
from core.config import settings
from core.privacy import resolve_data_region
from domain.ports.privacy_audit_repository import PrivacyAuditRepository
from domain.schemas.privacy import (
    DataResidencyPolicyResponse,
    SensitiveDataAuditRequest,
    SensitiveDataAuditResponse,
)

router = APIRouter(prefix="/internal/privacy", tags=["privacy"])


def _verify_api_key(x_internal_api_key: str = Header(default=None)) -> None:
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )


@router.post(
    "/audit",
    response_model=SensitiveDataAuditResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_sensitive_data_audit(
    payload: SensitiveDataAuditRequest,
    _: None = Depends(_verify_api_key),
    repository: PrivacyAuditRepository = Depends(get_privacy_audit_repository),
) -> SensitiveDataAuditResponse:
    return repository.record(payload)


@router.get(
    "/residency",
    response_model=DataResidencyPolicyResponse,
    status_code=status.HTTP_200_OK,
)
def resolve_residency_policy(
    country_code: str = Query(min_length=2, max_length=2),
    _: None = Depends(_verify_api_key),
) -> DataResidencyPolicyResponse:
    normalized_country = country_code.strip().upper()
    data_region = resolve_data_region(
        normalized_country,
        policies=settings.data_residency_policies,
        default_region=settings.default_data_region,
    )
    return DataResidencyPolicyResponse(
        country_code=normalized_country,
        data_region=data_region,
        storage_policy=f"pii:{normalized_country}:{data_region}",
    )
