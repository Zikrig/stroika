import re
from io import BytesIO

from openpyxl import Workbook

HEADERS = [
    "ID заявки",
    "С кем согласовано",
    "Дата/время заявки",
    "Дата потребности",
    "Подобъект",
    "Прораб",
    "Наименование от прораба",
    "Наименование по 1С",
    "Код 1С",
    "Запрошено",
    "Ед. изм.",
    "Со склада",
    "В закупку",
]

_ISO_DT = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?"
)


def _fmt_created_at(value: object) -> str:
    """Format ISO datetime as DD.MM.YYYY HH:MM."""
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    m = _ISO_DT.match(s)
    if m:
        y, mo, d, h, mi, _sec = m.groups()
        return f"{int(d):02d}.{int(mo):02d}.{int(y)} {int(h):02d}:{int(mi):02d}"
    return s[:16] if len(s) > 16 else s


def _name_from_foreman_cell(name: str | None) -> str:
    """Текст из сообщения или «файл» (эксель/ворд/голосовое/фото/видео/кружок)."""
    if not name or not name.strip():
        return "файл"
    if name.strip() == "Вложение без текстового описания":
        return "файл"
    return name.strip()


def _fmt_qty(value: object) -> float:
    """Число для ячейки (Запрошено и др.)."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_pdo_template(
    request: dict,
    foreman_display_name: str | None = None,
) -> bytes:
    """Строит Excel-форму с уже заполненными полями по умолчанию из заявки."""
    wb = Workbook()
    ws = wb.active
    ws.title = "PDO"
    ws.append(HEADERS)

    request_code = request.get("request_code") or ""
    approved_by = (request.get("approved_by") or "").strip()
    created_at = _fmt_created_at(request.get("created_at"))
    need_by = (request.get("need_by") or "").strip()
    subobject = (request.get("subobject_name") or "").strip()
    foreman_name = (foreman_display_name or "").strip()
    name_from_foreman = _name_from_foreman_cell(request.get("name_from_foreman"))
    nomenclature_1c = (request.get("nomenclature_1c") or "").strip()
    code_1c = (request.get("code_1c") or "").strip()
    requested_qty = _fmt_qty(request.get("requested_qty"))

    # Ед. изм., Со склада, В закупку — не подставляем, заполняет ПДО
    row = [
        request_code,
        approved_by,
        created_at,
        need_by,
        subobject,
        foreman_name,
        name_from_foreman,
        nomenclature_1c,
        code_1c,
        requested_qty,
        "",  # Ед. изм.
        "",  # Со склада
        "",  # В закупку
    ]
    ws.append(row)
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()
