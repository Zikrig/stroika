from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.domain.rules import RuleError, can_cancel


def apply_event(current_stage: StageCode, event_type: EventType, actor_role: Role) -> tuple[StatusCode, StageCode, Role | None]:
    if event_type == EventType.PDO_TAKEN:
        return (StatusCode.IN_PROGRESS, StageCode.PDO_PROCESSING, Role.PDO)
    if event_type == EventType.PDO_FORMALIZED:
        return (StatusCode.WAITING, StageCode.TRANSFERRED_TO_PROCUREMENT, Role.PROCUREMENT)
    if event_type == EventType.PROCUREMENT_TAKEN:
        return (StatusCode.IN_PROGRESS, StageCode.PROCUREMENT_IN_WORK, Role.PROCUREMENT)
    if event_type == EventType.PURCHASED:
        return (StatusCode.IN_PROGRESS, StageCode.PURCHASED, Role.PROCUREMENT)
    if event_type == EventType.SHIPPED:
        return (StatusCode.FORWARDED, StageCode.SHIPPED, Role.FOREMAN)
    if event_type == EventType.PARTIALLY_RECEIVED:
        return (StatusCode.IN_PROGRESS, StageCode.PARTIALLY_RECEIVED, Role.FOREMAN)
    if event_type == EventType.FULLY_RECEIVED:
        return (StatusCode.CLOSED, StageCode.FULLY_RECEIVED, None)
    if event_type == EventType.PAUSED:
        return (StatusCode.PAUSED, StageCode.PAUSED, None)
    if event_type == EventType.TERMINATED:
        return (StatusCode.TERMINATED, StageCode.TERMINATED, None)
    if event_type == EventType.RESUMED:
        return (StatusCode.IN_PROGRESS, current_stage, actor_role)
    if event_type == EventType.CANCELLED:
        if not can_cancel(current_stage, actor_role):
            raise RuleError("Отмена недоступна на текущем этапе")
        return (StatusCode.CANCELLED, StageCode.CANCELLED, None)
    if event_type == EventType.MANAGER_COMMENTED:
        return (StatusCode.IN_PROGRESS, current_stage, actor_role)
    raise RuleError(f"Событие не поддерживается: {event_type}")
