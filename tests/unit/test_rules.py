import pytest

from app.domain.enums import Role, StageCode
from app.domain.rules import RuleError, can_cancel, validate_pdo_formula, validate_received


def test_validate_formula_ok() -> None:
    validate_pdo_formula(10, 3, 7)


def test_validate_formula_fail() -> None:
    with pytest.raises(RuleError):
        validate_pdo_formula(10, 4, 7)


def test_validate_received_fail() -> None:
    with pytest.raises(RuleError):
        validate_received(10, 11)


def test_cancel_matrix() -> None:
    assert can_cancel(StageCode.CREATED, Role.FOREMAN) is True
    assert can_cancel(StageCode.PROCUREMENT_IN_WORK, Role.PROCUREMENT) is True
    assert can_cancel(StageCode.PURCHASED, Role.PROCUREMENT) is False
