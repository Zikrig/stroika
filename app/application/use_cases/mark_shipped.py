from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.infrastructure.repositories.request_repository import RequestRepository

from ._helpers import emit_event, ensure_not_paused


async def execute(requests: RequestRepository, request_id: str, actor_user_id: int, eta_arrival: str) -> dict | None:
    await ensure_not_paused(requests, request_id)
    await requests.update_state(
        request_id=request_id,
        status=StatusCode.FORWARDED,
        stage=StageCode.SHIPPED,
        responsible_role=Role.FOREMAN,
    )
    await emit_event(
        requests,
        request_id=request_id,
        event_type=EventType.SHIPPED,
        actor_user_id=actor_user_id,
        actor_role=Role.PROCUREMENT,
        payload={"eta_arrival": eta_arrival},
    )
    return await requests.get_request(request_id)
