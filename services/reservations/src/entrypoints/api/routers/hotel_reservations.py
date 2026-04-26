from functools import lru_cache
import logging
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlmodel import Session

from adapters.repositories.reservation_repository import SQLModelReservationRepository
from adapters.services.hotel_side_effects import (
    HttpReservationNotificationDispatcher,
    HttpReservationRefundDispatcher,
    NoOpReservationNotificationDispatcher,
    NoOpReservationRefundDispatcher,
)
from adapters.services.properties_client import PropertiesServiceClient
from adapters.services.users_client import UsersServiceClient
from core.auth import AuthenticatedUser, get_current_hotel_user
from core.config import settings
from db.session import get_session
from domain.ports.hotel_side_effects import (
    ReservationNotificationDispatcher,
    ReservationRefundDispatcher,
)
from domain.ports.property_service_client import PropertyServiceClient
from domain.schemas.reservation import (
    HotelReservationActionResponse,
    HotelReservationCancellationRequest,
    HotelReservationConfirmationRequest,
    HotelReservationDetailResponse,
    HotelReservationListItem,
    InternalNoteCreateRequest,
    InternalNoteResponse,
    ReservationCancellationReason,
    ReservationResponse,
    ReservationStatus,
)
from domain.services.cancellation_policy_refund import calculate_cancellation_refund
from domain.use_cases.add_internal_note import AddInternalNoteUseCase
from domain.use_cases.cancel_hotel_reservation import CancelHotelReservationUseCase
from domain.use_cases.confirm_hotel_reservation import ConfirmHotelReservationUseCase
from domain.use_cases.get_hotel_reservation_detail import GetHotelReservationDetailUseCase
from domain.use_cases.list_hotel_reservations import ListHotelReservationsUseCase
from entrypoints.api.routers.reservations import get_property_service_client
from errors import ReservationAuthorizationError, ReservationNotFoundError, ReservationStateConflictError

router = APIRouter(prefix="/hotel/reservations", tags=["hotel-reservations"])
logger = logging.getLogger(__name__)


def get_reservation_repository(session: Session = Depends(get_session)):
    return SQLModelReservationRepository(session)


def get_list_hotel_reservations_use_case(
    repository=Depends(get_reservation_repository),
):
    return ListHotelReservationsUseCase(repository)


def get_confirm_hotel_reservation_use_case(
    repository=Depends(get_reservation_repository),
):
    return ConfirmHotelReservationUseCase(repository)


def get_cancel_hotel_reservation_use_case(
    repository=Depends(get_reservation_repository),
):
    return CancelHotelReservationUseCase(repository)


def get_users_client() -> UsersServiceClient:
    return UsersServiceClient()


def get_properties_client() -> PropertiesServiceClient:
    return PropertiesServiceClient()


def get_hotel_reservation_detail_use_case(
    repository=Depends(get_reservation_repository),
    users_client: UsersServiceClient = Depends(get_users_client),
    properties_client: PropertiesServiceClient = Depends(get_properties_client),
):
    return GetHotelReservationDetailUseCase(repository, users_client, properties_client)


def get_add_internal_note_use_case(
    repository=Depends(get_reservation_repository),
):
    return AddInternalNoteUseCase(repository)


@lru_cache
def get_reservation_notification_dispatcher() -> ReservationNotificationDispatcher:
    if settings.notifications_service_url:
        return HttpReservationNotificationDispatcher()
    return NoOpReservationNotificationDispatcher()


@lru_cache
def get_reservation_refund_dispatcher() -> ReservationRefundDispatcher:
    if settings.payments_service_url:
        return HttpReservationRefundDispatcher()
    return NoOpReservationRefundDispatcher()


def _resolve_source_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


def _to_cents(amount: Decimal) -> int:
    return int(
        (amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def _dispatch_post_confirmation_effects(
    *,
    notification_dispatcher: ReservationNotificationDispatcher,
    traveler_id: UUID,
    reservation_id: UUID,
    source_ip: str | None,
    reason: str,
    locale: str | None,
) -> None:
    notification_dispatcher.dispatch_reservation_update(
        traveler_id=traveler_id,
        reservation_id=reservation_id,
        status=ReservationStatus.confirmed.value,
        reason=reason,
        locale=locale,
        source_ip=source_ip,
        refund_requested=False,
        refund_amount_in_cents=None,
    )


def _dispatch_post_cancellation_effects(
    *,
    refund_dispatcher: ReservationRefundDispatcher,
    notification_dispatcher: ReservationNotificationDispatcher,
    property_client: PropertyServiceClient,
    reservation: ReservationResponse,
    traveler_id: UUID,
    reservation_id: UUID,
    source_ip: str | None,
    reason: str,
    locale: str | None,
    reason_code: str | None,
    reason_note: str | None,
    refund_requested: bool,
) -> None:
    refund_amount = None
    should_request_refund = refund_requested
    if refund_requested:
        try:
            policy = property_client.get_cancellation_policy(reservation.id_property)
            calculated_refund, _, _, _, _ = calculate_cancellation_refund(
                total_price=reservation.total_price,
                check_in_date=reservation.check_in_date,
                policy=policy,
            )
            refund_amount = _to_cents(calculated_refund)
        except Exception:
            logger.exception(
                "Failed to calculate policy refund for cancelled reservation %s; using full refund fallback",
                reservation_id,
            )
            refund_amount = _to_cents(reservation.total_price)

        should_request_refund = bool(refund_amount and refund_amount > 0)
        if should_request_refund:
            try:
                refund_response = refund_dispatcher.request_refund(
                    reservation_id=reservation_id,
                    amount_in_cents=refund_amount,
                    cancellation_reason=reason,
                    idempotency_key=f"hotel-cancel:{reservation_id}",
                    source_ip=source_ip,
                )
                if refund_response and refund_response.get("amount_in_cents") is not None:
                    refund_amount = refund_response.get("amount_in_cents")
            except Exception:
                logger.exception(
                    "Failed to request refund for cancelled reservation %s",
                    reservation_id,
                )

    notification_dispatcher.dispatch_reservation_update(
        traveler_id=traveler_id,
        reservation_id=reservation_id,
        status=ReservationStatus.cancelled.value,
        reason=reason,
        locale=locale,
        reason_code=reason_code,
        reason_note=reason_note,
        source_ip=source_ip,
        refund_requested=should_request_refund,
        refund_amount_in_cents=refund_amount,
    )


@router.get("", response_model=list[HotelReservationListItem], status_code=status.HTTP_200_OK)
def list_hotel_reservations(
    property_id: UUID = Query(..., alias="propertyId"),
    status_filter: str | None = Query(default=None, alias="status"),
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: ListHotelReservationsUseCase = Depends(get_list_hotel_reservations_use_case),
) -> list[HotelReservationListItem]:
    return use_case.execute(property_id, status=status_filter)


@router.post("/{reservation_id}/confirm", response_model=HotelReservationActionResponse)
def confirm_hotel_reservation(
    reservation_id: UUID,
    payload: HotelReservationConfirmationRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: ConfirmHotelReservationUseCase = Depends(get_confirm_hotel_reservation_use_case),
    notification_dispatcher: ReservationNotificationDispatcher = Depends(
        get_reservation_notification_dispatcher
    ),
) -> HotelReservationActionResponse:
    try:
        result = use_case.execute(
            reservation_id,
            actor_user_id=user.id,
            source_ip=_resolve_source_ip(request),
            reason=payload.reason,
        )
        background_tasks.add_task(
            _dispatch_post_confirmation_effects,
            notification_dispatcher=notification_dispatcher,
            traveler_id=result.reservation.id_traveler,
            reservation_id=result.reservation.id,
            source_ip=_resolve_source_ip(request),
            reason=result.reason,
            locale=payload.locale,
        )
        return result
    except ReservationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ReservationStateConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/{reservation_id}/cancel", response_model=HotelReservationActionResponse)
def cancel_hotel_reservation(
    reservation_id: UUID,
    payload: HotelReservationCancellationRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: CancelHotelReservationUseCase = Depends(get_cancel_hotel_reservation_use_case),
    property_client: PropertyServiceClient = Depends(get_property_service_client),
    notification_dispatcher: ReservationNotificationDispatcher = Depends(
        get_reservation_notification_dispatcher
    ),
    refund_dispatcher: ReservationRefundDispatcher = Depends(get_reservation_refund_dispatcher),
) -> HotelReservationActionResponse:
    try:
        result = use_case.execute(
            reservation_id,
            actor_user_id=user.id,
            source_ip=_resolve_source_ip(request),
            reason=ReservationCancellationReason(payload.reason),
            note=payload.note,
        )
        background_tasks.add_task(
            _dispatch_post_cancellation_effects,
            refund_dispatcher=refund_dispatcher,
            notification_dispatcher=notification_dispatcher,
            property_client=property_client,
            reservation=result.reservation,
            traveler_id=result.reservation.id_traveler,
            reservation_id=result.reservation.id,
            source_ip=_resolve_source_ip(request),
            reason=result.reason,
            locale=payload.locale,
            reason_code=payload.reason.value,
            reason_note=payload.note.strip() if payload.note else None,
            refund_requested=result.refund_requested,
        )
        return result
    except ReservationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ReservationStateConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/{reservation_id}", response_model=HotelReservationDetailResponse, status_code=status.HTTP_200_OK)
def get_hotel_reservation_detail(
    reservation_id: UUID,
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: GetHotelReservationDetailUseCase = Depends(get_hotel_reservation_detail_use_case),
) -> HotelReservationDetailResponse:
    try:
        return use_case.execute(reservation_id, owner_hotel_id=user.id)
    except ReservationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ReservationAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/{reservation_id}/notes", response_model=InternalNoteResponse, status_code=status.HTTP_201_CREATED)
def add_internal_note(
    reservation_id: UUID,
    payload: InternalNoteCreateRequest,
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: AddInternalNoteUseCase = Depends(get_add_internal_note_use_case),
) -> InternalNoteResponse:
    try:
        return use_case.execute(
            reservation_id=reservation_id,
            content=payload.content,
            author_user_id=user.id,
            author_name=None,
        )
    except ReservationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
