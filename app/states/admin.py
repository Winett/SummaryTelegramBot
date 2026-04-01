from aiogram.fsm.state import State, StatesGroup

class AdminAddState(StatesGroup):
    add_admin = State()

class AdminRemoveState(StatesGroup):
    remove_admin = State()