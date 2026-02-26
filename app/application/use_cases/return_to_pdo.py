from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.infrastructure.repositories.request_repository import RequestRepository

from ._helpers import emit_event, ensure_not_paused


async def execute(requests: RequestRepository, request_id: str, actor_user_id: int) -> dict | None:
    await ensure_not_paused(requests, request_id)
    await requests.update_state(
        request_id=request_id,
        status=StatusCode.WAITING,
        stage=StageCode.PDO_PROCESSING,
        responsible_role=Role.PDO,
    )
    await emit_event(
        requests=requests,
        request_id=request_id,
        event_type=EventType.RETURNED_TO_PDO,
        actor_user_id=actor_user_id,
        actor_role=Role.PROCUREMENT,
        payload={},
    )
    return await requests.get_request(request_id)
