import logging


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Заглушаем очень подробные DEBUG-логи aiosqlite вида
    # "executing functools.partial(...)" / "operation ... completed".
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
