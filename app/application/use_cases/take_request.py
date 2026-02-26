from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.infrastructure.repositories.request_repository import RequestRepository

from ._helpers import emit_event, ensure_not_paused


async def take_by_pdo(requests: RequestRepository, request_id: str, actor_user_id: int) -> dict | None:
    await ensure_not_paused(requests, request_id)
    await requests.update_state(
        request_id=request_id,
        status=StatusCode.IN_PROGRESS,
        stage=StageCode.PDO_PROCESSING,
        responsible_role=Role.PDO,
    )
    await emit_event(requests, request_id, EventType.PDO_TAKEN, actor_user_id, Role.PDO, {})
    return await requests.get_request(request_id)


async def take_by_procurement(requests: RequestRepository, request_id: str, actor_user_id: int) -> dict | None:
    await ensure_not_paused(requests, request_id)
    await requests.update_state(
        request_id=request_id,
        status=StatusCode.IN_PROGRESS,
        stage=StageCode.PROCUREMENT_IN_WORK,
        responsible_role=Role.PROCUREMENT,
    )
    await emit_event(requests, request_id, EventType.PROCUREMENT_TAKEN, actor_user_id, Role.PROCUREMENT, {})
    return await requests.get_request(request_id)
