import re


def next_parent_code(last_code: str | None) -> str:
    if not last_code:
        return "IG-1"
    match = re.match(r"IG-(\d+)$", last_code)
    if not match:
        raise ValueError(f"Некорректный ID: {last_code}")
    return f"IG-{int(match.group(1)) + 1}"


def child_code(parent_code: str, index: int) -> str:
    if index < 1:
        raise ValueError("Индекс дочерней заявки должен быть >= 1")
    return f"{parent_code}-{index}"
