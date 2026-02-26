from app.application.dto import CreateRequestInput
from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.domain.services.id_generator import next_parent_code
from app.infrastructure.repositories.request_repository import RequestRepository

from ._helpers import emit_event


async def execute(requests: RequestRepository, data: CreateRequestInput) -> dict:
    last_code = await requests.get_last_parent_code()
    request_code = next_parent_code(last_code)
    request_id = await requests.create_request(
        {
            "request_code": request_code,
            "chat_id": data.chat_id,
            "foreman_user_id": data.foreman_user_id,
            "object_name": data.object_name,
            "name_from_foreman": data.description,
            "subobject_name": data.subobject_name,
            "requested_qty": data.requested_qty,
            "unit": data.unit,
            "need_by": data.need_by,
            "remaining_qty": data.requested_qty,
            "status_code": StatusCode.WAITING.value,
            "stage_code": StageCode.CREATED.value,
            "responsible_role": Role.PDO.value,
        }
    )
    event_id = await emit_event(
        requests,
        request_id=request_id,
        event_type=EventType.REQUEST_CREATED,
        actor_user_id=data.foreman_user_id,
        actor_role=Role.FOREMAN,
        payload={
            "request_code": request_code,
            "description": data.description,
            "attachments_count": len(data.attachments),
        },
    )
    if data.attachments:
        await requests.add_attachments(request_id=request_id, event_id=event_id, attachments=data.attachments)
    return await requests.get_request(request_id)
