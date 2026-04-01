from aiogram.fsm.state import State, StatesGroup

class SummaryManualState(StatesGroup):
    waiting_for_date = State()
