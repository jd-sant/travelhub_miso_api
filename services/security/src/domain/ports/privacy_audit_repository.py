from abc import ABC, abstractmethod

from domain.schemas.privacy import SensitiveDataAuditRequest, SensitiveDataAuditResponse


class PrivacyAuditRepository(ABC):
    @abstractmethod
    def record(self, payload: SensitiveDataAuditRequest) -> SensitiveDataAuditResponse:
        pass
