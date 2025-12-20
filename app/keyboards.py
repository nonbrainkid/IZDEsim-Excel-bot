from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu():
    keyboard = [
        [KeyboardButton(text="📤 Выгрузить Excel")],
        [KeyboardButton(text="📊 Скачать Excel")],
        [KeyboardButton(text="🚪 Выход")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)