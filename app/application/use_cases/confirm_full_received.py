from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.infrastructure.repositories.request_repository import RequestRepository

from ._helpers import emit_event, ensure_not_paused


async def execute(requests: RequestRepository, request_id: str, actor_user_id: int) -> dict | None:
    request = await ensure_not_paused(requests, request_id)
    requested = float(request["requested_qty"])
    await requests.update_state(
        request_id=request_id,
        status=StatusCode.CLOSED,
        stage=StageCode.FULLY_RECEIVED,
        responsible_role=None,
        extra={"received_total_qty": requested, "remaining_qty": 0.0, "closed_at": request["updated_at"]},
    )
    await emit_event(
        requests,
        request_id=request_id,
        event_type=EventType.FULLY_RECEIVED,
        actor_user_id=actor_user_id,
        actor_role=Role.FOREMAN,
        payload={"received_total_qty": requested, "remaining_qty": 0.0},
    )
    return await requests.get_request(request_id)
