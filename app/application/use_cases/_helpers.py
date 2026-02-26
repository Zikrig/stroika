from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.infrastructure.repositories.request_repository import RequestRepository


async def emit_event(
    requests: RequestRepository,
    request_id: str,
    event_type: EventType,
    actor_user_id: int,
    actor_role: Role,
    payload: dict,
) -> str:
    return await requests.append_event(
        request_id=request_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        payload=payload,
    )


async def ensure_not_paused(requests: RequestRepository, request_id: str) -> dict:
    request = await requests.get_request(request_id)
    if not request:
        raise ValueError("Заявка не найдена")
    if request.get("status_code") == StatusCode.PAUSED.value or request.get("stage_code") == StageCode.PAUSED.value:
        raise ValueError("Заявка на паузе. Доступны только действия руководителя.")
    return request
