from __future__ import annotations

import re
from datetime import datetime

from app.domain.enums import EventType, StageCode, StatusCode
from app.domain.services.role_guard import role_title

# ISO datetime: 2026-02-27T23:01:11.819762+00:00 или 2026-02-27 23:01:11
_ISO_DT = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?"
)


def _fmt_date(value: object) -> str:
    """Format ISO or date string as DD.MM.YYYY HH:MM or DD.MM.YYYY if date-only."""
    if value is None:
        return "-"
    s = str(value).strip()
    if not s:
        return "-"
    m = _ISO_DT.match(s)
    if m:
        y, mo, d, h, mi, sec = m.groups()
        sec = (sec or "0").split(".")[0]
        return f"{int(d):02d}.{int(mo):02d}.{int(y)} {int(h):02d}:{int(mi):02d}"
    try:
        part = s.split()[0] if s else ""
        dt = datetime.strptime(part, "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return s[:16] if len(s) > 16 else s


_STATUS_TITLES = {
    StatusCode.WAITING.value: "Ждет действия",
    StatusCode.IN_PROGRESS.value: "В работе",
    StatusCode.FORWARDED.value: "Передано дальше",
    StatusCode.CLOSED.value: "Закрыто",
    StatusCode.CANCELLED.value: "Отменено",
    StatusCode.PAUSED.value: "Приостановлено",
    StatusCode.TERMINATED.value: "Прекращено",
}

_STATUS_MARKERS = {
    StatusCode.WAITING.value: "🔴",
    StatusCode.IN_PROGRESS.value: "🟡",
    StatusCode.FORWARDED.value: "🔵",
    StatusCode.CLOSED.value: "⚪",
    StatusCode.CANCELLED.value: "⚫",
    StatusCode.PAUSED.value: "⛔",
    StatusCode.TERMINATED.value: "⚫",
}

_STAGE_TITLES = {
    StageCode.CREATED.value: "Создано",
    StageCode.PDO_PROCESSING.value: "ПДО в работе",
    StageCode.TRANSFERRED_TO_PROCUREMENT.value: "Передано в закупку",
    StageCode.PROCUREMENT_IN_WORK.value: "Закупка в работе",
    StageCode.PURCHASED.value: "Закуплено",
    StageCode.SHIPPED.value: "Отгружено поставщиком",
    StageCode.PARTIALLY_RECEIVED.value: "Получено частично",
    StageCode.FULLY_RECEIVED.value: "Получено полностью",
    StageCode.CANCELLED.value: "Отменено",
    StageCode.PAUSED.value: "Приостановлено",
    StageCode.TERMINATED.value: "Прекращено руководителем",
}


def _fmt_qty(value: object) -> str:
    try:
        num = float(value or 0)
    except (TypeError, ValueError):
        return "-"
    if num.is_integer():
        return str(int(num))
    return f"{num:.2f}".rstrip("0").rstrip(".")


def _latest_procurement_dates(events: list[dict] | None) -> tuple[str, str, str]:
    eta_shipping = "-"
    shipped_at = "-"
    eta_arrival = "-"
    for event in events or []:
        payload = event.get("payload_json") or {}
        event_type = event.get("event_type")
        if event_type == EventType.PURCHASED.value and payload.get("eta_shipping"):
            eta_shipping = _fmt_date(payload["eta_shipping"])
        if event_type == EventType.SHIPPED.value:
            if payload.get("eta_arrival"):
                eta_arrival = _fmt_date(payload["eta_arrival"])
            if event.get("created_at"):
                shipped_at = _fmt_date(event["created_at"])
    return eta_shipping, shipped_at, eta_arrival


def _format_foreman(request: dict, foreman_info: dict | None) -> str:
    if not request.get("foreman_user_id"):
        return "-"
    uid = request["foreman_user_id"]
    if foreman_info:
        name = foreman_info.get("display_name") or foreman_info.get("full_name") or str(uid)
        username = foreman_info.get("username")
        if username:
            return f"{name} (@{username})"
        return f"{name} (tg://user?id={uid})"
    return str(uid)


def render_request_card(
    request: dict,
    events: list[dict] | None = None,
    attachments_summary: dict | None = None,
    note: str | None = None,
    note_label: str = "Комментарий",
    foreman_info: dict | None = None,
) -> str:
    unit = request.get("unit") or ""
    status_code = str(request.get("status_code") or "")
    stage_code = str(request.get("stage_code") or "")
    eta_shipping, shipped_at, eta_arrival = _latest_procurement_dates(events)

    lines = [
        f"ID: {request.get('request_code', '-')}",
        f"👷 Прораб: {_format_foreman(request, foreman_info)}",
        f"🏗 Объект: {request.get('object_name') or '-'}",
        f"🎯 Подобъект: {request.get('subobject_name') or '-'}",
        f"📝 Наименование от прораба: {request.get('name_from_foreman') or '-'}",
        f"📦 Номенклатура 1С: {request.get('nomenclature_1c') or '-'}",
        f"🔢 Код 1С: {request.get('code_1c') or '-'}",
        f"📏 Запрошено: {_fmt_qty(request.get('requested_qty'))} {unit}".rstrip(),
        f"📅 Требуется до: {request.get('need_by') or '-'}",
        f"🕒 Дата создания: {_fmt_date(request.get('created_at'))}",
        (
            "📎 Вложения: -"
            if not attachments_summary or not attachments_summary.get("total")
            else (
                "📎 Вложения: "
                f"{attachments_summary['total']} ("
                + ", ".join(f"{k}:{v}" for k, v in attachments_summary.get("by_type", {}).items())
                + ")"
            )
        ),
        "",
        f"Статус: {_STATUS_MARKERS.get(status_code, '⚪')} {_STATUS_TITLES.get(status_code, status_code or '-')}",
        f"Этап: {_STAGE_TITLES.get(stage_code, stage_code or '-')}",
        (
            "👤 Ответственный: -"
            if not request.get("responsible_role")
            else f"👤 Ответственный: {role_title(request['responsible_role'])}"
        ),
        (
            f"📦 Потребность: {_fmt_qty(request.get('requested_qty'))} / "
            f"{_fmt_qty(request.get('from_stock_qty'))} / {_fmt_qty(request.get('to_purchase_qty'))} {unit}"
        ).rstrip(),
        f"🚚 Закупка: ETA отгрузки {eta_shipping} / Отгружено {shipped_at} / ETA на объект {eta_arrival}",
        (
            f"📍 На объекте: Получено {_fmt_qty(request.get('received_total_qty'))} / "
            f"Остаток {_fmt_qty(request.get('remaining_qty'))} {unit}"
        ).rstrip(),
    ]
    if note:
        lines.extend(["", f"{note_label}: {note}"])
    return "\n".join(lines)


def render_container_card(container: dict, child_codes: list[str]) -> str:
    lines = [
        f"📦 КОНТЕЙНЕР {container.get('request_code', '-')}",
        f"🏗 Объект: {container.get('object_name') or '-'}",
        f"🎯 Подобъект: {container.get('subobject_name') or '-'}",
        f"🕒 Дата создания: {_fmt_date(container.get('created_at'))}",
        "",
        "Разбит ПДО на заявки:",
    ]
    for code in child_codes:
        lines.append(f"- {code}")
    return "\n".join(lines)
