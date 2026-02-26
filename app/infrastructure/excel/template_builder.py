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


def build_pdo_template(request_code: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "PDO"
    ws.append(HEADERS)
    ws.append([request_code, "", "", "", "", "", "", "", "", "", "", "", ""])
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()
