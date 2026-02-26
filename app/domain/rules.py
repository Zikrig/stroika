from app.domain.enums import Role, StageCode, StatusCode


class RuleError(ValueError):
    pass


def validate_pdo_formula(requested_qty: float, from_stock_qty: float, to_purchase_qty: float) -> None:
    if round(requested_qty, 6) != round(from_stock_qty + to_purchase_qty, 6):
        raise RuleError("Запрошено должно быть равно Со склада + В закупку")


def validate_received(requested_qty: float, new_received_total: float) -> None:
    if new_received_total < 0:
        raise RuleError("Получено не может быть отрицательным")
    if new_received_total - requested_qty > 1e-6:
        raise RuleError("Получено не может превышать запрошенное количество")


def can_cancel(stage: StageCode, role: Role) -> bool:
    return (
        (role == Role.FOREMAN and stage == StageCode.CREATED)
        or (role == Role.PDO and stage in {StageCode.CREATED, StageCode.PDO_PROCESSING})
        or (role == Role.PROCUREMENT and stage in {StageCode.TRANSFERRED_TO_PROCUREMENT, StageCode.PROCUREMENT_IN_WORK})
    )


def validate_transition_to_closed(status: StatusCode, stage: StageCode) -> None:
    if status in {StatusCode.CANCELLED, StatusCode.CLOSED, StatusCode.TERMINATED}:
        raise RuleError(f"Заявка уже закрыта: {stage}")
