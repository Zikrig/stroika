from aiogram.fsm.state import State, StatesGroup


class RoleOnboardingStates(StatesGroup):
    waiting_foreman_name = State()


class ForemanCreateStates(StatesGroup):
    waiting_description = State()
    waiting_qty = State()
    waiting_subobject = State()
    waiting_need_by = State()


class GroupMenuStates(StatesGroup):
    waiting_search_query = State()
    waiting_history_code = State()


class AdminPanelStates(StatesGroup):
    waiting_register_chat_id = State()
    waiting_set_role_chat_id = State()
    waiting_set_role_user_id = State()
    waiting_set_role_role = State()


class ForemanEditStates(StatesGroup):
    waiting_edit_description = State()
    waiting_edit_qty = State()
    waiting_edit_subobject = State()
    waiting_edit_need_by = State()


class ActionInputStates(StatesGroup):
    waiting_pdo_excel = State()
    waiting_partial_qty = State()
    waiting_purchase_date = State()
    waiting_ship_date = State()
    waiting_cancel_reason = State()
    waiting_manager_comment = State()
    waiting_pause_reason = State()
    waiting_resume_comment = State()
    waiting_terminate_reason = State()
