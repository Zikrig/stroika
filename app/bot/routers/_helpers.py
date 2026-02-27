"""Shared helpers for routers."""

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey


def private_fsm(state: FSMContext, bot_id: int, user_id: int) -> FSMContext:
    """Return an FSMContext keyed to the user's private chat."""
    key = StorageKey(bot_id=bot_id, chat_id=user_id, user_id=user_id)
    return FSMContext(storage=state.storage, key=key)
