from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.domain.rules import can_cancel
from app.infrastructure.repositories.request_repository import RequestRepository

from ._helpers import emit_event, ensure_not_paused


async def execute(requests: RequestRepository, request_id: str, actor_user_id: int, actor_role: Role, reason: str) -> dict | None:
    request = await ensure_not_paused(requests, request_id)
    stage = StageCode(request["stage_code"])
    if not can_cancel(stage, actor_role):
        raise ValueError("Отмена недоступна для вашей роли на этом этапе")
    await requests.update_state(
        request_id=request_id,
        status=StatusCode.CANCELLED,
        stage=StageCode.CANCELLED,
        responsible_role=None,
        extra={"closed_at": request["updated_at"], "remaining_qty": 0.0},
    )
    await emit_event(
        requests,
        request_id=request_id,
        event_type=EventType.CANCELLED,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        payload={"reason": reason},
    )
    return await requests.get_request(request_id)
