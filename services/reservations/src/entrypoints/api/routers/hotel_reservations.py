from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlmodel import Session

from adapters.repositories.reservation_repository import SQLModelReservationRepository
from adapters.services.hotel_side_effects import (
    NoOpReservationNotificationDispatcher,
    NoOpReservationRefundDispatcher,
    SqsReservationNotificationDispatcher,
    SqsReservationRefundDispatcher,
)
from core.auth import AuthenticatedUser, get_current_hotel_user
from core.config import settings
from db.session import get_session
from domain.ports.hotel_side_effects import (
    ReservationNotificationDispatcher,
    ReservationRefundDispatcher,
)
from domain.schemas.reservation import (
    HotelReservationActionResponse,
    HotelReservationCancellationRequest,
    HotelReservationConfirmationRequest,
    HotelReservationListItem,
    ReservationCancellationReason,
    ReservationStatus,
)
from domain.use_cases.cancel_hotel_reservation import CancelHotelReservationUseCase
from domain.use_cases.confirm_hotel_reservation import ConfirmHotelReservationUseCase
from domain.use_cases.list_hotel_reservations import ListHotelReservationsUseCase
from errors import ReservationNotFoundError, ReservationStateConflictError

router = APIRouter(prefix="/hotel/reservations", tags=["hotel-reservations"])


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


@lru_cache
def get_reservation_notification_dispatcher() -> ReservationNotificationDispatcher:
    if settings.notifications_queue_url:
        return SqsReservationNotificationDispatcher()
    return NoOpReservationNotificationDispatcher()


@lru_cache
def get_reservation_refund_dispatcher() -> ReservationRefundDispatcher:
    if settings.payments_queue_url:
        return SqsReservationRefundDispatcher()
    return NoOpReservationRefundDispatcher()


def _resolve_source_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


def _dispatch_post_confirmation_effects(
    *,
    notification_dispatcher: ReservationNotificationDispatcher,
    traveler_id: UUID,
    reservation_id: UUID,
    source_ip: str | None,
    reason: str,
) -> None:
    notification_dispatcher.dispatch_reservation_update(
        traveler_id=traveler_id,
        reservation_id=reservation_id,
        status=ReservationStatus.confirmed.value,
        reason=reason,
        source_ip=source_ip,
        refund_requested=False,
    )


def _dispatch_post_cancellation_effects(
    *,
    refund_dispatcher: ReservationRefundDispatcher,
    notification_dispatcher: ReservationNotificationDispatcher,
    traveler_id: UUID,
    reservation_id: UUID,
    source_ip: str | None,
    reason: str,
    refund_requested: bool,
) -> None:
    if refund_requested:
        refund_dispatcher.request_refund(
            reservation_id=reservation_id,
            cancellation_reason=reason,
            source_ip=source_ip,
        )

    notification_dispatcher.dispatch_reservation_update(
        traveler_id=traveler_id,
        reservation_id=reservation_id,
        status=ReservationStatus.cancelled.value,
        reason=reason,
        source_ip=source_ip,
        refund_requested=refund_requested,
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
            traveler_id=result.reservation.id_traveler,
            reservation_id=result.reservation.id,
            source_ip=_resolve_source_ip(request),
            reason=result.reason,
            refund_requested=result.refund_requested,
        )
        return result
    except ReservationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ReservationStateConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
