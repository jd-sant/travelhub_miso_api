from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from uuid import UUID


class PricingServiceClient(ABC):
    @abstractmethod
    def get_effective_price(
        self,
        property_id: UUID,
        check_in: datetime,
        check_out: datetime,
        guests: int,
    ) -> tuple[Decimal, str] | None:
        pass
