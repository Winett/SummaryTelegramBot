from aiogram.fsm.state import State, StatesGroup

class SettingModelLLMState(StatesGroup):
    waiting_for_model = State()
