import json
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlmodel import Session, select

from adapters.models import InventoryCalendar, PricingChangeLog, RateCalendar, RatePlan, RoomType
from domain.schemas.pricing import (
    PricingApplyRequest,
    PricingHistoryItem,
    PricingPreviewRequest,
    PricingPreviewResponse,
    PricingTargetOption,
)
from errors import (
    PricingAuthorizationError,
    PricingConflictError,
    PricingTargetNotFoundError,
    PricingValidationError,
)


class SQLModelPricingManagementRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_targets(self, owned_property_ids: Iterable[UUID]) -> list[PricingTargetOption]:
        property_ids = list(owned_property_ids)
        if not property_ids:
            return []
        statement = (
            select(RatePlan, RoomType)
            .join(RoomType, RoomType.id == RatePlan.room_type_id)
            .where(RoomType.property_id.in_(property_ids))
            .where(RoomType.is_active.is_(True))
            .where(RatePlan.is_active.is_(True))
        )
        rows = self.session.exec(statement).all()
        property_names = self._property_names(property_ids)
        return [
            PricingTargetOption(
                property_id=room_type.property_id,
                property_name=property_names.get(room_type.property_id, str(room_type.property_id)),
                room_type_id=room_type.id,
                room_type_name=room_type.name,
                rate_plan_id=rate_plan.id,
                rate_plan_name=rate_plan.name,
                currency=rate_plan.currency,
                base_price=rate_plan.base_price,
            )
            for rate_plan, room_type in rows
        ]

    def build_preview(
        self,
        payload: PricingPreviewRequest,
        owned_property_ids: set[UUID],
    ) -> PricingPreviewResponse:
        target = self._get_target(payload.property_id, payload.rate_plan_id, owned_property_ids)
        self._validate_range(payload.start_date, payload.end_date)
        current_base = target["rate_plan"].base_price
        proposed_base = payload.proposed_base_price or current_base
        final_price = self._apply_discount(
            proposed_base,
            payload.discount_type,
            payload.discount_value,
        )
        sellable_units = self._sellable_units(target["room_type"].id, payload.start_date, payload.end_date)
        days_affected = (payload.end_date - payload.start_date).days + 1
        projected_before = current_base * sellable_units
        projected_after = final_price * sellable_units
        delta = projected_after - projected_before
        requires_confirmation = days_affected > 7 or (
            payload.discount_type == "percentage" and (payload.discount_value or Decimal("0")) >= Decimal("20")
        ) or (
            payload.discount_type == "fixed" and (payload.discount_value or Decimal("0")) >= Decimal("50")
        )
        return PricingPreviewResponse(
            property_id=target["room_type"].property_id,
            property_name=target["property_name"],
            room_type_id=target["room_type"].id,
            room_type_name=target["room_type"].name,
            rate_plan_id=target["rate_plan"].id,
            rate_plan_name=target["rate_plan"].name,
            currency=target["rate_plan"].currency,
            start_date=payload.start_date,
            end_date=payload.end_date,
            days_affected=days_affected,
            current_base_price=current_base,
            proposed_base_price=proposed_base,
            discount_type=payload.discount_type,
            discount_value=payload.discount_value,
            final_price=final_price,
            projected_revenue_before=projected_before,
            projected_revenue_after=projected_after,
            projected_revenue_delta=delta,
            sellable_units=sellable_units,
            requires_confirmation=requires_confirmation,
            impact_summary=(
                "Se actualizarán "
                f"{days_affected} días con una tarifa final de {final_price} "
                f"y un ingreso proyectado de {projected_after}."
            ),
        )

    def apply_pricing(
        self,
        payload: PricingApplyRequest,
        owned_property_ids: set[UUID],
        actor_user_id: UUID,
        actor_email: str,
        actor_ip: str | None = None,
        request_checksum: str | None = None,
    ) -> tuple[PricingPreviewResponse, PricingHistoryItem]:
        preview = self.build_preview(payload, owned_property_ids)
        if preview.requires_confirmation and not payload.confirmation_acknowledged:
            raise PricingValidationError("Debes confirmar el cambio antes de aplicarlo")

        target = self._get_target(payload.property_id, payload.rate_plan_id, owned_property_ids)
        rate_plan: RatePlan = target["rate_plan"]
        previous_base_price = rate_plan.base_price
        previous_snapshot = self._snapshot_calendar(rate_plan.id, payload.start_date, payload.end_date)
        rate_plan.base_price = preview.proposed_base_price
        self._upsert_calendar_prices(rate_plan.id, payload.start_date, payload.end_date, preview.final_price)

        change_log = PricingChangeLog(
            property_id=preview.property_id,
            property_name=preview.property_name,
            room_type_id=preview.room_type_id,
            room_type_name=preview.room_type_name,
            rate_plan_id=preview.rate_plan_id,
            rate_plan_name=preview.rate_plan_name,
            currency=preview.currency,
            rule_name=payload.rule_name,
            start_date=payload.start_date,
            end_date=payload.end_date,
            previous_base_price=str(previous_base_price),
            new_base_price=str(preview.proposed_base_price),
            discount_type=payload.discount_type,
            discount_value=str(payload.discount_value) if payload.discount_value is not None else None,
            final_price=str(preview.final_price),
            projected_revenue_before=str(preview.projected_revenue_before),
            projected_revenue_after=str(preview.projected_revenue_after),
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            actor_ip=actor_ip,
            device_label=payload.device_label,
            device_platform=payload.device_platform,
            request_checksum=request_checksum,
            previous_calendar_snapshot=json.dumps(previous_snapshot),
        )
        self.session.add(change_log)
        self.session.add(rate_plan)
        self.session.commit()
        self.session.refresh(change_log)
        return preview, self._map_history(change_log)

    def list_history(self, owned_property_ids: set[UUID]) -> list[PricingHistoryItem]:
        if not owned_property_ids:
            return []
        statement = (
            select(PricingChangeLog)
            .where(PricingChangeLog.property_id.in_(owned_property_ids))
            .order_by(PricingChangeLog.created_at.desc())
        )
        return [self._map_history(item) for item in self.session.exec(statement).all()]

    def revert_change(self, change_id: UUID, owned_property_ids: set[UUID]) -> PricingHistoryItem:
        change = self.session.get(PricingChangeLog, change_id)
        if change is None or change.property_id not in owned_property_ids:
            raise PricingTargetNotFoundError("Cambio no encontrado")
        if change.reverted_at is not None:
            raise PricingConflictError("Este cambio ya fue revertido")
        if self._has_newer_active_overlapping_change(change):
            raise PricingConflictError(
                "No puedes revertir este cambio porque existe un ajuste posterior activo sobre el mismo rango"
            )

        rate_plan = self.session.get(RatePlan, change.rate_plan_id)
        if rate_plan is None:
            raise PricingTargetNotFoundError("Plan tarifario no encontrado")
        rate_plan.base_price = Decimal(change.previous_base_price)
        snapshot = json.loads(change.previous_calendar_snapshot)
        for item in snapshot:
            row = self.session.exec(
                select(RateCalendar)
                .where(RateCalendar.rate_plan_id == change.rate_plan_id)
                .where(RateCalendar.date == date.fromisoformat(item["date"]))
            ).first()
            if item["existed"]:
                if row is None:
                    row = RateCalendar(
                        rate_plan_id=change.rate_plan_id,
                        date=date.fromisoformat(item["date"]),
                        price=Decimal(item["price"]),
                    )
                    self.session.add(row)
                else:
                    row.price = Decimal(item["price"])
                    self.session.add(row)
            elif row is not None:
                self.session.delete(row)

        change.reverted_at = datetime.now(UTC)
        self.session.add(rate_plan)
        self.session.add(change)
        self.session.commit()
        self.session.refresh(change)
        return self._map_history(change)

    def _has_newer_active_overlapping_change(self, change: PricingChangeLog) -> bool:
        candidates = self.session.exec(
            select(PricingChangeLog)
            .where(PricingChangeLog.rate_plan_id == change.rate_plan_id)
            .where(PricingChangeLog.reverted_at.is_(None))
            .where(PricingChangeLog.created_at > change.created_at)
        ).all()
        for candidate in candidates:
            if candidate.start_date <= change.end_date and candidate.end_date >= change.start_date:
                return True
        return False

    def _get_target(self, property_id: UUID, rate_plan_id: UUID, owned_property_ids: set[UUID]) -> dict:
        if property_id not in owned_property_ids:
            raise PricingAuthorizationError("No puedes gestionar tarifas de esta propiedad")
        statement = (
            select(RatePlan, RoomType)
            .join(RoomType, RoomType.id == RatePlan.room_type_id)
            .where(RatePlan.id == rate_plan_id)
            .where(RoomType.property_id == property_id)
            .where(RatePlan.is_active.is_(True))
            .where(RoomType.is_active.is_(True))
        )
        row = self.session.exec(statement).first()
        if row is None:
            raise PricingTargetNotFoundError("Objetivo tarifario no encontrado")
        rate_plan, room_type = row
        property_name = self._property_names([property_id]).get(property_id, str(property_id))
        return {"rate_plan": rate_plan, "room_type": room_type, "property_name": property_name}

    def _property_names(self, property_ids: Iterable[UUID]) -> dict[UUID, str]:
        from adapters.models import Property

        statement = select(Property).where(Property.id.in_(list(property_ids)))
        return {row.id: row.name for row in self.session.exec(statement).all()}

    def _validate_range(self, start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise PricingValidationError("La fecha final debe ser posterior o igual a la inicial")
        if (end_date - start_date).days > 60:
            raise PricingValidationError("El rango máximo permitido es de 61 días")

    def _apply_discount(
        self,
        proposed_base_price: Decimal,
        discount_type: str | None,
        discount_value: Decimal | None,
    ) -> Decimal:
        final_price = proposed_base_price
        if discount_type == "percentage":
            value = discount_value or Decimal("0")
            if value > Decimal("100"):
                raise PricingValidationError("El descuento porcentual no puede ser mayor a 100")
            final_price = proposed_base_price * (Decimal("1") - (value / Decimal("100")))
        elif discount_type == "fixed":
            value = discount_value or Decimal("0")
            final_price = proposed_base_price - value
        if final_price <= Decimal("0"):
            raise PricingValidationError("La tarifa final debe ser mayor a cero")
        return final_price.quantize(Decimal("0.01"))

    def _sellable_units(self, room_type_id: UUID, start_date: date, end_date: date) -> int:
        statement = (
            select(InventoryCalendar)
            .where(InventoryCalendar.room_type_id == room_type_id)
            .where(InventoryCalendar.date >= start_date)
            .where(InventoryCalendar.date <= end_date)
        )
        rows = self.session.exec(statement).all()
        if not rows:
            return 0
        return sum(max(0, row.available_units - row.blocked_units) for row in rows)

    def _snapshot_calendar(self, rate_plan_id: UUID, start_date: date, end_date: date) -> list[dict]:
        snapshot: list[dict] = []
        cursor = start_date
        while cursor <= end_date:
            row = self.session.exec(
                select(RateCalendar)
                .where(RateCalendar.rate_plan_id == rate_plan_id)
                .where(RateCalendar.date == cursor)
            ).first()
            snapshot.append(
                {
                    "date": cursor.isoformat(),
                    "existed": row is not None,
                    "price": str(row.price) if row is not None else None,
                }
            )
            cursor += timedelta(days=1)
        return snapshot

    def _upsert_calendar_prices(self, rate_plan_id: UUID, start_date: date, end_date: date, final_price: Decimal) -> None:
        cursor = start_date
        while cursor <= end_date:
            row = self.session.exec(
                select(RateCalendar)
                .where(RateCalendar.rate_plan_id == rate_plan_id)
                .where(RateCalendar.date == cursor)
            ).first()
            if row is None:
                row = RateCalendar(rate_plan_id=rate_plan_id, date=cursor, price=final_price)
                self.session.add(row)
            else:
                row.price = final_price
                self.session.add(row)
            cursor += timedelta(days=1)

    def _map_history(self, item: PricingChangeLog) -> PricingHistoryItem:
        return PricingHistoryItem(
            id=item.id,
            property_id=item.property_id,
            property_name=item.property_name,
            room_type_name=item.room_type_name,
            rate_plan_name=item.rate_plan_name,
            currency=item.currency,
            rule_name=item.rule_name,
            start_date=item.start_date,
            end_date=item.end_date,
            previous_base_price=Decimal(item.previous_base_price),
            new_base_price=Decimal(item.new_base_price),
            discount_type=item.discount_type,
            discount_value=Decimal(item.discount_value) if item.discount_value is not None else None,
            final_price=Decimal(item.final_price),
            projected_revenue_before=Decimal(item.projected_revenue_before),
            projected_revenue_after=Decimal(item.projected_revenue_after),
            actor_user_id=item.actor_user_id,
            actor_email=item.actor_email,
            actor_ip=item.actor_ip,
            device_label=item.device_label,
            device_platform=item.device_platform,
            request_checksum=item.request_checksum,
            created_at=item.created_at,
            reverted_at=item.reverted_at,
            can_revert=item.reverted_at is None,
        )
