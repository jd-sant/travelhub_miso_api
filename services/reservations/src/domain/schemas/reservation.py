from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ReservationStatus(str, Enum):
    pending_payment = "pending_payment"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"


class ReservationCancellationReason(str, Enum):
    maintenance = "maintenance"
    overbooking = "overbooking"
    hotel_policy = "hotel_policy"
    other = "other"
    modification_pending_payment = "modification_pending_payment"
    modification_confirmed = "modification_confirmed"
    additional_charge_failed = "additional_charge_failed"
    cancel_requested = "cancel_requested"
    refund_pending = "refund_pending"
    refund_completed = "refund_completed"
    refund_failed = "refund_failed"


class CancellationPolicyType(str, Enum):
    non_refundable = "non_refundable"
    partial_refund = "partial_refund"
    full_refund = "full_refund"


class ReservationEventType(str, Enum):
    modification_previewed = "modification_previewed"
    cancellation_previewed = "cancellation_previewed"
    modification_confirmed = "modification_confirmed"
    cancellation_confirmed = "cancellation_confirmed"
    status_changed = "status_changed"


class ReservationEventResult(str, Enum):
    success = "success"
    rejected = "rejected"
    failed = "failed"


class ReservationCommandType(str, Enum):
    modification_confirm = "modification_confirm"
    cancellation_confirm = "cancellation_confirm"


class FinancialResultStatus(str, Enum):
    succeeded = "succeeded"
    failed = "failed"


class ReservationCreateRequest(BaseModel):
    id_traveler: UUID
    id_property: UUID
    id_room: UUID
    check_in_date: datetime
    check_out_date: datetime
    number_of_guests: int = Field(ge=1)
    currency: str = Field(max_length=3)


class ReservationStatusUpdateRequest(BaseModel):
    status: ReservationStatus


class HotelReservationListItem(BaseModel):
    id: UUID
    id_traveler: UUID
    id_property: UUID
    id_room: UUID
    check_in_date: datetime
    check_out_date: datetime
    number_of_guests: int
    total_price: Decimal
    currency: str
    status: str
    hold_expires_at: datetime
    created_at: datetime
    updated_at: datetime


class HotelReservationConfirmationRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class HotelReservationCancellationRequest(BaseModel):
    reason: ReservationCancellationReason
    note: str | None = Field(default=None, max_length=500)


class ReservationPriceBreakdown(BaseModel):
    total_price: Decimal
    currency: str


class ReservationPolicySnapshot(BaseModel):
    policy_type: CancellationPolicyType
    minimum_notice_hours: int = Field(ge=0, default=24)
    penalty_percentage: Decimal = Field(ge=0, le=100, default=Decimal("0"))
    timezone: str = Field(default="UTC")


class ReservationModificationPreviewRequest(BaseModel):
    check_in_date: datetime
    check_out_date: datetime
    number_of_guests: int = Field(ge=1)


class ReservationModificationPreviewResponse(BaseModel):
    reservation_id: UUID
    reservation_before: "ReservationResponse"
    reservation_after_preview: "ReservationResponse"
    price_before: ReservationPriceBreakdown
    price_after: ReservationPriceBreakdown
    delta_amount: Decimal
    requires_additional_charge: bool
    estimated_refund_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    policy_applied: ReservationPolicySnapshot
    change_allowed: bool
    reasons: list[str] = Field(default_factory=list)


class ReservationCancellationPreviewResponse(BaseModel):
    reservation_id: UUID
    policy_applied: ReservationPolicySnapshot
    refund_amount: Decimal = Field(ge=0)
    penalty_amount: Decimal = Field(ge=0)
    refund_type: CancellationPolicyType
    eligible_until: datetime
    change_allowed: bool
    reasons: list[str] = Field(default_factory=list)


class ReservationModificationConfirmRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=128)
    check_in_date: datetime
    check_out_date: datetime
    number_of_guests: int = Field(ge=1)


class ReservationCancellationConfirmRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=128)
    reason: str | None = Field(default=None, max_length=255)


class ReservationRefundResultRequest(BaseModel):
    status: FinancialResultStatus
    refund_id: UUID | None = None
    amount_in_cents: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=255)


class ReservationAdditionalChargeResultRequest(BaseModel):
    status: FinancialResultStatus
    payment_id: UUID | None = None
    amount_in_cents: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=255)


class ReservationEventCreateRequest(BaseModel):
    reservation_id: UUID
    event_type: ReservationEventType
    actor_user_id: UUID | None = None
    source_ip: str | None = None
    result: ReservationEventResult = ReservationEventResult.success
    before_payload: dict | None = None
    after_payload: dict | None = None


class ReservationEventResponse(BaseModel):
    id: UUID
    reservation_id: UUID
    event_type: ReservationEventType
    actor_user_id: UUID | None
    source_ip: str | None
    result: ReservationEventResult
    before_payload: dict | None
    after_payload: dict | None
    created_at: datetime


class ReservationResponse(BaseModel):
    id: UUID
    id_traveler: UUID
    id_property: UUID
    id_room: UUID
    check_in_date: datetime
    check_out_date: datetime
    number_of_guests: int
    total_price: Decimal
    currency: str
    status: str
    hold_expires_at: datetime
    version: int = 1
    created_at: datetime
    updated_at: datetime


class ReservationSummary(BaseModel):
    id: UUID
    status: str
    total_price: Decimal
    currency: str
    check_in_date: datetime
    check_out_date: datetime
    hold_expires_at: datetime
    created_at: datetime


class ReservationCheckStatusResponse(BaseModel):
    reservation: ReservationResponse
    status_before: str
    status_after: str
    action_applied: str


class HostReservationItem(BaseModel):
    id: UUID
    reservation_number: str
    id_property: UUID
    id_room: UUID
    id_traveler: UUID
    guest_full_name: str | None = None
    room_type: str | None = None
    check_in_date: datetime
    check_out_date: datetime
    number_of_guests: int
    total_price: Decimal
    currency: str
    status: str
    created_at: datetime


class HostReservationsPage(BaseModel):
    items: list[HostReservationItem]
    total: int
    page: int
    page_size: int


class HostMetrics(BaseModel):
    active_reservations: int
    occupancy_rate: float
    revenue_amount: Decimal
    revenue_currency: str | None = None
    available_currencies: list[str] = []
    average_daily_rate: Decimal
    total_nights: int


class HostRevenueBucket(BaseModel):
    bucket: datetime
    revenue: Decimal
    reservations: int


class HostRevenueTrends(BaseModel):
    granularity: str
    currency: str | None = None
    available_currencies: list[str] = []
    buckets: list[HostRevenueBucket]


class HotelReservationActionResponse(BaseModel):
    reservation: ReservationResponse
    status_before: str
    status_after: str
    action_applied: str
    reason: str
    refund_requested: bool = False


class ReservationChangeRecord(BaseModel):
    id: UUID
    reservation_id: UUID
    action: str
    previous_status: str
    new_status: str
    reason: str
    actor_user_id: UUID | None = None
    source_ip: str | None = None
    created_at: datetime

class ReservationConfirmResponse(BaseModel):
    reservation: ReservationResponse
    status_before: str
    status_after: str
    action_applied: str
    idempotency_key: str
    additional_charge_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    refund_amount: Decimal = Field(default=Decimal("0.00"), ge=0)


class ReservationHistoryResponse(BaseModel):
    reservation_id: UUID
    events: list[ReservationEventResponse]


class ReservationWithDetailsResponse(BaseModel):
    id: UUID
    reservation: ReservationResponse
    property_name: str | None = None
    property_cover_image_url: str | None = None


ReservationModificationPreviewResponse.model_rebuild()

