from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from adapters.services.payments_client import PaymentsServiceClient
from adapters.services.properties_client import PropertiesServiceClient
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import HostMetrics, HostRevenueBucket, HostRevenueTrends


class ComputeHostMetricsUseCase:
    def __init__(
        self,
        repository: ReservationRepository,
        properties_client: PropertiesServiceClient,
        payments_client: PaymentsServiceClient,
    ):
        self.repository = repository
        self.properties_client = properties_client
        self.payments_client = payments_client

    def execute(
        self,
        *,
        owner_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> HostMetrics:
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        properties = self.properties_client.list_by_owner(owner_id)
        property_ids = [UUID(p["id"]) for p in properties]
        if not property_ids:
            return HostMetrics(
                active_reservations=0,
                occupancy_rate=0.0,
                revenue_amount=Decimal("0.00"),
                revenue_currency=None,
                average_daily_rate=Decimal("0.00"),
                total_nights=0,
            )

        operational = self.repository.operational_metrics_for_properties(
            property_ids, start_date=start_date, end_date=end_date
        )
        reservation_ids = self.repository.list_confirmed_ids_by_properties(
            property_ids, start_date=start_date, end_date=end_date
        )
        aggregate = self.payments_client.aggregate(
            reservation_ids,
            status="confirmed",
            start_date=start_date,
            end_date=end_date,
        )

        revenue_amount = Decimal(aggregate["total_amount_cents"]) / Decimal("100")
        currency = aggregate.get("currency")
        total_nights = operational["total_nights"]
        average_daily_rate = (
            (revenue_amount / Decimal(total_nights)).quantize(Decimal("0.01"))
            if total_nights > 0
            else Decimal("0.00")
        )

        room_capacity = sum(_room_count(p) for p in properties)
        period_days = max((end_date - start_date).days, 1)
        capacity_room_nights = room_capacity * period_days
        occupancy_rate = (
            round(total_nights / capacity_room_nights, 4)
            if capacity_room_nights > 0
            else 0.0
        )

        return HostMetrics(
            active_reservations=operational["active_reservations"],
            occupancy_rate=occupancy_rate,
            revenue_amount=revenue_amount.quantize(Decimal("0.01")),
            revenue_currency=currency,
            average_daily_rate=average_daily_rate,
            total_nights=total_nights,
        )


class ComputeRevenueTrendsUseCase:
    def __init__(
        self,
        repository: ReservationRepository,
        properties_client: PropertiesServiceClient,
        payments_client: PaymentsServiceClient,
    ):
        self.repository = repository
        self.properties_client = properties_client
        self.payments_client = payments_client

    def execute(
        self,
        *,
        owner_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        granularity: str = "week",
    ) -> HostRevenueTrends:
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        property_ids = self.properties_client.get_owned_property_ids(owner_id)
        if not property_ids:
            return HostRevenueTrends(granularity=granularity, currency=None, buckets=[])

        reservation_ids = self.repository.list_confirmed_ids_by_properties(
            property_ids, start_date=start_date, end_date=end_date
        )
        aggregate = self.payments_client.aggregate(
            reservation_ids,
            status="confirmed",
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
        )
        buckets = [
            HostRevenueBucket(
                bucket=_parse_dt(b["bucket"]),
                revenue=(Decimal(b["amount_cents"]) / Decimal("100")).quantize(
                    Decimal("0.01")
                ),
                reservations=b["count"],
            )
            for b in aggregate.get("buckets", [])
        ]
        return HostRevenueTrends(
            granularity=granularity,
            currency=aggregate.get("currency"),
            buckets=buckets,
        )


def _room_count(property_payload: dict) -> int:
    bedrooms = property_payload.get("bedrooms") or 0
    return max(int(bedrooms), 1)


def _parse_dt(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
