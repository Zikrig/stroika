from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.domain.rules import validate_received
from app.infrastructure.repositories.request_repository import RequestRepository

from ._helpers import emit_event, ensure_not_paused


async def execute(requests: RequestRepository, request_id: str, actor_user_id: int, delta_qty: float) -> dict | None:
    request = await ensure_not_paused(requests, request_id)
    new_total = float(request["received_total_qty"]) + delta_qty
    requested = float(request["requested_qty"])
    validate_received(requested, new_total)
    remaining = max(0.0, requested - new_total)
    await requests.update_state(
        request_id=request_id,
        status=StatusCode.IN_PROGRESS,
        stage=StageCode.PARTIALLY_RECEIVED,
        responsible_role=Role.FOREMAN,
        extra={"received_total_qty": new_total, "remaining_qty": remaining},
    )
    await emit_event(
        requests,
        request_id=request_id,
        event_type=EventType.PARTIALLY_RECEIVED,
        actor_user_id=actor_user_id,
        actor_role=Role.FOREMAN,
        payload={"delta_qty": delta_qty, "received_total_qty": new_total, "remaining_qty": remaining},
    )
    return await requests.get_request(request_id)
