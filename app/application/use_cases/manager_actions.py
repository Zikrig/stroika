from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.infrastructure.repositories.request_repository import RequestRepository

from ._helpers import emit_event


async def comment(requests: RequestRepository, request_id: str, actor_user_id: int, text: str) -> dict | None:
    await emit_event(
        requests=requests,
        request_id=request_id,
        event_type=EventType.MANAGER_COMMENTED,
        actor_user_id=actor_user_id,
        actor_role=Role.MANAGER,
        payload={"comment": text},
    )
    return await requests.get_request(request_id)


async def terminate(requests: RequestRepository, request_id: str, actor_user_id: int, reason: str) -> dict | None:
    request = await requests.get_request(request_id)
    if not request:
        return None
    await requests.update_state(
        request_id=request_id,
        status=StatusCode.TERMINATED,
        stage=StageCode.TERMINATED,
        responsible_role=None,
        extra={"closed_at": request["updated_at"], "remaining_qty": 0.0},
    )
    await emit_event(
        requests=requests,
        request_id=request_id,
        event_type=EventType.TERMINATED,
        actor_user_id=actor_user_id,
        actor_role=Role.MANAGER,
        payload={"reason": reason},
    )
    return await requests.get_request(request_id)
