import json
from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError

from domain.ports.reservation_scheduler import ReservationScheduler


class NoOpReservationScheduler(ReservationScheduler):
    def schedule_reservation_expiration(self, reservation_id: str) -> str:
        return f"noop-verify-reservation-{reservation_id}"

    def cancel_reservation_expiration(self, reservation_id: str) -> None:
        return None


class EventBridgeReservationScheduler(ReservationScheduler):
    def __init__(
        self,
        *,
        aws_region: str,
        lambda_arn: str,
        scheduler_role_arn: str,
        api_base_url: str,
        delay_minutes: int = 15,
    ) -> None:
        import boto3

        self._client = boto3.client("scheduler", region_name=aws_region)
        self._lambda_arn = lambda_arn
        self._scheduler_role_arn = scheduler_role_arn
        self._api_base_url = api_base_url.rstrip("/")
        self._delay_minutes = delay_minutes

    def schedule_reservation_expiration(self, reservation_id: str) -> str:
        fire_at = datetime.now(timezone.utc) + timedelta(minutes=self._delay_minutes)
        schedule_expression = f"at({fire_at.strftime('%Y-%m-%dT%H:%M:%S')})"
        schedule_name = f"verify-reservation-{reservation_id}"

        payload = {
            "reservation_id": reservation_id,
            "api_url": f"{self._api_base_url}/api/v1/reservations/{reservation_id}/checkstatus",
        }

        try:
            self._client.create_schedule(
                Name=schedule_name,
                ScheduleExpression=schedule_expression,
                ScheduleExpressionTimezone="UTC",
                Target={
                    "Arn": self._lambda_arn,
                    "RoleArn": self._scheduler_role_arn,
                    "Input": json.dumps(payload),
                    "RetryPolicy": {
                        "MaximumRetryAttempts": 2,
                        "MaximumEventAgeInSeconds": 300,
                    },
                },
                FlexibleTimeWindow={"Mode": "OFF"},
                ActionAfterCompletion="DELETE",
            )
            return schedule_name
        except ClientError as exc:
            message = exc.response.get("Error", {}).get("Message", "Unknown AWS scheduler error")
            raise RuntimeError(f"Error creating schedule: {message}") from exc

    def cancel_reservation_expiration(self, reservation_id: str) -> None:
        schedule_name = f"verify-reservation-{reservation_id}"
        try:
            self._client.delete_schedule(Name=schedule_name)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code != "ResourceNotFoundException":
                raise RuntimeError("Error deleting schedule") from exc
