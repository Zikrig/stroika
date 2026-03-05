from dataclasses import dataclass
from dataclasses import field
from typing import Any


@dataclass(slots=True)
class CreateRequestInput:
    chat_id: int
    foreman_user_id: int
    object_name: str
    description: str
    requested_qty: float = 0.0
    unit: str = "шт"
    subobject_name: str | None = None
    need_by: str | None = None
    approved_by: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
