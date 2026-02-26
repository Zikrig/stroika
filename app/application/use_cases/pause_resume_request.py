from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.infrastructure.repositories.request_repository import RequestRepository

from ._helpers import emit_event


async def pause(requests: RequestRepository, request_id: str, actor_user_id: int, reason: str) -> dict | None:
    request = await requests.get_request(request_id)
    if not request:
        return None
    if request["status_code"] == StatusCode.PAUSED.value:
        raise ValueError("Заявка уже находится на паузе")
    await requests.update_state(
        request_id=request_id,
        status=StatusCode.PAUSED,
        stage=StageCode.PAUSED,
        responsible_role=None,
        extra={
            "paused_previous_status": request["status_code"],
            "paused_previous_stage": request["stage_code"],
            "paused_previous_role": request["responsible_role"],
        },
    )
    await emit_event(
        requests,
        request_id=request_id,
        event_type=EventType.PAUSED,
        actor_user_id=actor_user_id,
        actor_role=Role.MANAGER,
        payload={"reason": reason},
    )
    return await requests.get_request(request_id)


async def resume(requests: RequestRepository, request_id: str, actor_user_id: int, comment: str) -> dict | None:
    request = await requests.get_request(request_id)
    if not request:
        return None
    if request["status_code"] != StatusCode.PAUSED.value:
        raise ValueError("Снять паузу можно только у приостановленной заявки")
    stage = StageCode(request["paused_previous_stage"] or StageCode.CREATED.value)
    status = StatusCode(request["paused_previous_status"] or StatusCode.IN_PROGRESS.value)
    role = request["paused_previous_role"]
    await requests.update_state(
        request_id=request_id,
        status=status,
        stage=stage,
        responsible_role=None if role is None else Role(role),
        extra={"paused_previous_status": None, "paused_previous_stage": None, "paused_previous_role": None},
    )
    await emit_event(
        requests,
        request_id=request_id,
        event_type=EventType.RESUMED,
        actor_user_id=actor_user_id,
        actor_role=Role.MANAGER,
        payload={"comment": comment},
    )
    return await requests.get_request(request_id)
