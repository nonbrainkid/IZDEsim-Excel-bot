from aiogram.fsm.state import State, StatesGroup

class AuthStates(StatesGroup):
    waiting_email = State()
    waiting_code = State()   # Ожидание ввода кода верификации
    in_menu = State()
    waiting_file = State()