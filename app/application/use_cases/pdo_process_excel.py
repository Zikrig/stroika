from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.domain.services.id_generator import child_code
from app.infrastructure.repositories.request_repository import RequestRepository

from ._helpers import emit_event, ensure_not_paused


async def execute(requests: RequestRepository, parent_request: dict, rows: list[dict], actor_user_id: int) -> list[dict]:
    await ensure_not_paused(requests, parent_request["id"])
    request_id = parent_request["id"]
    created: list[dict] = []

    if len(rows) == 1:
        row = rows[0]
        from_stock = float(row.get("from_stock_qty") or 0)
        to_purchase = float(row.get("to_purchase_qty") or 0)
        if from_stock > 0 and to_purchase <= 0:
            status = StatusCode.FORWARDED
            stage = StageCode.SHIPPED
            responsible_role = Role.FOREMAN
        else:
            status = StatusCode.WAITING
            stage = StageCode.TRANSFERRED_TO_PROCUREMENT
            responsible_role = Role.PROCUREMENT
        await requests.update_state(
            request_id,
            status=status,
            stage=stage,
            responsible_role=responsible_role,
            extra={
                "subobject_name": row["subobject_name"],
                "name_from_foreman": row["name_from_foreman"],
                "nomenclature_1c": row["nomenclature_1c"],
                "code_1c": row["code_1c"],
                "requested_qty": row["requested_qty"],
                "unit": row["unit"],
                "from_stock_qty": row["from_stock_qty"],
                "to_purchase_qty": row["to_purchase_qty"],
                "remaining_qty": row["requested_qty"],
                "need_by": row["need_by"],
            },
        )
        await requests.insert_request_item(request_id, 1, row)
        await emit_event(
            requests,
            request_id=request_id,
            event_type=EventType.PDO_FORMALIZED,
            actor_user_id=actor_user_id,
            actor_role=Role.PDO,
            payload={"rows": rows},
        )
        updated = await requests.get_request(request_id)
        if updated:
            created.append(updated)
        return created

    await requests.update_state(
        request_id,
        status=StatusCode.CLOSED,
        stage=StageCode.FULLY_RECEIVED,
        responsible_role=None,
        extra={"is_container": 1, "closed_at": parent_request["updated_at"], "remaining_qty": 0},
    )
    await emit_event(
        requests,
        request_id=request_id,
        event_type=EventType.PDO_FORMALIZED,
        actor_user_id=actor_user_id,
        actor_role=Role.PDO,
        payload={"mode": "container", "children_count": len(rows)},
    )

    for idx, row in enumerate(rows, start=1):
        code = child_code(parent_request["request_code"], idx)
        child_id = await requests.create_request(
            {
                "request_code": code,
                "chat_id": parent_request["chat_id"],
                "parent_request_id": request_id,
                "foreman_user_id": parent_request["foreman_user_id"],
                "object_name": parent_request["object_name"],
                "subobject_name": row["subobject_name"],
                "name_from_foreman": row["name_from_foreman"],
                "nomenclature_1c": row["nomenclature_1c"],
                "code_1c": row["code_1c"],
                "requested_qty": row["requested_qty"],
                "unit": row["unit"],
                "from_stock_qty": row["from_stock_qty"],
                "to_purchase_qty": row["to_purchase_qty"],
                "remaining_qty": row["requested_qty"],
                "need_by": row["need_by"],
                "status_code": StatusCode.WAITING.value,
                "stage_code": StageCode.TRANSFERRED_TO_PROCUREMENT.value,
                "responsible_role": Role.PROCUREMENT.value,
            }
        )
        await requests.insert_request_item(child_id, idx, row)
        await emit_event(
            requests,
            request_id=child_id,
            event_type=EventType.PDO_FORMALIZED,
            actor_user_id=actor_user_id,
            actor_role=Role.PDO,
            payload={"source_container": parent_request["request_code"]},
        )
        child = await requests.get_request(child_id)
        if child:
            created.append(child)
    return created
