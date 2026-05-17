from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from adapters.services.payments_client import PaymentsServiceClient
from adapters.services.properties_client import PropertiesServiceClient
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import HostMetrics, HostRevenueBucket, HostRevenueTrends

RevenueMode = Literal['confirmed_reservations', 'collected_payments']


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
        currency: str | None = None,
        revenue_mode: RevenueMode = 'confirmed_reservations',
    ) -> HostMetrics:
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        properties = self.properties_client.list_by_owner(owner_id)
        property_ids = [UUID(p['id']) for p in properties]
        if not property_ids:
            return HostMetrics(
                active_reservations=0,
                occupancy_rate=0.0,
                revenue_amount=Decimal('0.00'),
                revenue_currency=None,
                available_currencies=[],
                average_daily_rate=Decimal('0.00'),
                total_nights=0,
            )

        operational = self.repository.operational_metrics_for_properties(
            property_ids, start_date=start_date, end_date=end_date
        )

        revenue_amount, currency_filter, available_currencies = _compute_revenue_amount(
            repository=self.repository,
            payments_client=self.payments_client,
            property_ids=property_ids,
            start_date=start_date,
            end_date=end_date,
            currency=currency,
            revenue_mode=revenue_mode,
        )

        total_nights = operational['total_nights']
        average_daily_rate = (
            (revenue_amount / Decimal(total_nights)).quantize(Decimal('0.01'))
            if total_nights > 0
            else Decimal('0.00')
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
            active_reservations=operational['active_reservations'],
            occupancy_rate=occupancy_rate,
            revenue_amount=revenue_amount.quantize(Decimal('0.01')),
            revenue_currency=currency_filter,
            available_currencies=available_currencies,
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
        granularity: str = 'week',
        currency: str | None = None,
        revenue_mode: RevenueMode = 'confirmed_reservations',
    ) -> HostRevenueTrends:
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        property_ids = self.properties_client.get_owned_property_ids(owner_id)
        if not property_ids:
            return HostRevenueTrends(
                granularity=granularity,
                currency=None,
                available_currencies=[],
                buckets=[],
            )

        if revenue_mode == 'collected_payments':
            return _payments_revenue_trends(
                repository=self.repository,
                payments_client=self.payments_client,
                property_ids=property_ids,
                start_date=start_date,
                end_date=end_date,
                granularity=granularity,
                currency=currency,
            )

        return _reservations_revenue_trends(
            repository=self.repository,
            property_ids=property_ids,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            currency=currency,
        )


def _compute_revenue_amount(
    *,
    repository: ReservationRepository,
    payments_client: PaymentsServiceClient,
    property_ids: list[UUID],
    start_date: datetime,
    end_date: datetime,
    currency: str | None,
    revenue_mode: RevenueMode,
) -> tuple[Decimal, str | None, list[str]]:
    if revenue_mode == 'collected_payments':
        reservation_ids = repository.list_confirmed_ids_by_properties(
            property_ids, start_date=start_date, end_date=end_date
        )
        payments = payments_client.list_by_reservations(
            reservation_ids,
            status='confirmed',
        )
        items = payments.get('items', [])
        available_currencies = payments.get('available_currencies', [])

        if currency:
            currency_filter = currency.upper()
        elif available_currencies:
            currency_filter = available_currencies[0]
        else:
            currency_filter = None

        if currency_filter:
            items = [it for it in items if it.get('currency') == currency_filter]

        total_cents = sum(int(it['amount_in_cents']) for it in items)
        return Decimal(total_cents) / Decimal('100'), currency_filter, available_currencies

    rows = repository.list_confirmed_revenue_rows_by_properties(
        property_ids, start_date=start_date, end_date=end_date
    )
    available_currencies = sorted({row_currency.upper() for _, _, _, row_currency in rows})

    if currency:
        currency_filter = currency.upper()
    elif available_currencies:
        currency_filter = available_currencies[0]
    else:
        currency_filter = None

    if currency_filter:
        rows = [row for row in rows if row[3].upper() == currency_filter]

    total_amount = sum((amount for _, _, amount, _ in rows), Decimal('0.00'))
    return total_amount, currency_filter, available_currencies


def _payments_revenue_trends(
    *,
    repository: ReservationRepository,
    payments_client: PaymentsServiceClient,
    property_ids: list[UUID],
    start_date: datetime,
    end_date: datetime,
    granularity: str,
    currency: str | None,
) -> HostRevenueTrends:
    rows = repository.list_confirmed_with_check_in_by_properties(
        property_ids, start_date=start_date, end_date=end_date
    )
    if not rows:
        return HostRevenueTrends(
            granularity=granularity,
            currency=None,
            available_currencies=[],
            buckets=[],
        )

    check_in_by_id: dict[UUID, datetime] = {rid: ci for rid, ci in rows}
    payments = payments_client.list_by_reservations(
        list(check_in_by_id.keys()),
        status='confirmed',
    )
    items = payments.get('items', [])
    available_currencies = payments.get('available_currencies', [])

    if currency:
        currency_filter = currency.upper()
    elif available_currencies:
        currency_filter = available_currencies[0]
    else:
        currency_filter = None

    grouped: dict[datetime, dict[str, Decimal | int]] = {}
    for item in items:
        if currency_filter and item.get('currency') != currency_filter:
            continue
        res_id = UUID(str(item['reservation_id']))
        check_in = check_in_by_id.get(res_id)
        if check_in is None:
            continue
        key = _truncate(check_in, granularity)
        entry = grouped.setdefault(key, {'amount': Decimal('0.00'), 'count': 0})
        entry['amount'] += Decimal(int(item['amount_in_cents'])) / Decimal('100')
        entry['count'] += 1

    buckets = [
        HostRevenueBucket(
            bucket=key,
            revenue=Decimal(val['amount']).quantize(Decimal('0.01')),
            reservations=int(val['count']),
        )
        for key, val in sorted(grouped.items())
    ]
    return HostRevenueTrends(
        granularity=granularity,
        currency=currency_filter,
        available_currencies=available_currencies,
        buckets=buckets,
    )


def _reservations_revenue_trends(
    *,
    repository: ReservationRepository,
    property_ids: list[UUID],
    start_date: datetime,
    end_date: datetime,
    granularity: str,
    currency: str | None,
) -> HostRevenueTrends:
    rows = repository.list_confirmed_revenue_rows_by_properties(
        property_ids, start_date=start_date, end_date=end_date
    )
    if not rows:
        return HostRevenueTrends(
            granularity=granularity,
            currency=None,
            available_currencies=[],
            buckets=[],
        )

    available_currencies = sorted({row_currency.upper() for _, _, _, row_currency in rows})

    if currency:
        currency_filter = currency.upper()
    elif available_currencies:
        currency_filter = available_currencies[0]
    else:
        currency_filter = None

    grouped: dict[datetime, dict[str, Decimal | int]] = {}
    for _, check_in, total_price, row_currency in rows:
        if currency_filter and row_currency.upper() != currency_filter:
            continue
        key = _truncate(check_in, granularity)
        entry = grouped.setdefault(key, {'amount': Decimal('0.00'), 'count': 0})
        entry['amount'] += total_price
        entry['count'] += 1

    buckets = [
        HostRevenueBucket(
            bucket=key,
            revenue=Decimal(val['amount']).quantize(Decimal('0.01')),
            reservations=int(val['count']),
        )
        for key, val in sorted(grouped.items())
    ]
    return HostRevenueTrends(
        granularity=granularity,
        currency=currency_filter,
        available_currencies=available_currencies,
        buckets=buckets,
    )


def _room_count(property_payload: dict) -> int:
    bedrooms = property_payload.get('bedrooms') or 0
    return max(int(bedrooms), 1)


def _truncate(moment: datetime, granularity: str) -> datetime:
    base = moment.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None) if moment.tzinfo else moment.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == 'day':
        return base
    if granularity == 'week':
        return base - timedelta(days=base.weekday())
    if granularity == 'month':
        return base.replace(day=1)
    return base
