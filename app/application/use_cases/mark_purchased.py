from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.infrastructure.repositories.request_repository import RequestRepository

from ._helpers import emit_event, ensure_not_paused


async def execute(requests: RequestRepository, request_id: str, actor_user_id: int, eta_shipping: str) -> dict | None:
    await ensure_not_paused(requests, request_id)
    await requests.update_state(
        request_id=request_id,
        status=StatusCode.IN_PROGRESS,
        stage=StageCode.PURCHASED,
        responsible_role=Role.PROCUREMENT,
        extra={},
    )
    await emit_event(
        requests,
        request_id=request_id,
        event_type=EventType.PURCHASED,
        actor_user_id=actor_user_id,
        actor_role=Role.PROCUREMENT,
        payload={"eta_shipping": eta_shipping},
    )
    return await requests.get_request(request_id)
