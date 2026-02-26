from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.enums import Role, StageCode, StatusCode


@dataclass(slots=True)
class Request:
    id: str
    request_code: str
    chat_id: int
    parent_request_id: str | None
    is_container: bool
    foreman_user_id: int | None
    object_name: str
    subobject_name: str | None
    name_from_foreman: str | None
    nomenclature_1c: str | None
    code_1c: str | None
    requested_qty: float
    unit: str
    need_by: str | None
    from_stock_qty: float
    to_purchase_qty: float
    received_total_qty: float
    remaining_qty: float
    status_code: StatusCode
    stage_code: StageCode
    responsible_role: Role | None
    paused_previous_status: StatusCode | None
    paused_previous_stage: StageCode | None
    paused_previous_role: Role | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class RequestEvent:
    id: str
    request_id: str
    event_type: str
    actor_user_id: int
    actor_role: str
    payload: dict[str, Any]
    created_at: datetime
