import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from validators import (
    validate_login_response,
    validate_export_response,
    validate_upload_response,
    validate_file_extension,
    AuthenticationError,
    ValidationError,
    ServerError,
    APIError,
    NetworkError,
    get_user_friendly_error)
from service import APIService
from config import config  # ✅ ИСПРАВЛЕНО: импортируем экземпляр config

logger = logging.getLogger(__name__)

# Хранилище токенов пользователей
user_tokens = {}


# FSM States
class AuthStates(StatesGroup):
    waiting_email = State()
    waiting_password = State()
    in_menu = State()
    waiting_file = State()


# Клавиатуры
def get_main_menu():
    keyboard = [
        [KeyboardButton(text="📤 Выгрузить Excel")],
        [KeyboardButton(text="📊 Скачать Excel")],
        [KeyboardButton(text="🚪 Выход")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# Handlers
async def cmd_start(message: types.Message, state: FSMContext):
    """Команда /start"""
    await state.clear()
    await message.answer(
        "👋 Привет! Я бот для работы с Excel файлами.\n\n"
        "Для начала работы введите почту:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AuthStates.waiting_email)


async def process_login(message: types.Message, state: FSMContext):
    """Обработка логина"""
    username = message.text.strip()
    await state.update_data(username=username)
    await message.answer("🔑 Теперь введите пароль:")
    await state.set_state(AuthStates.waiting_password)


async def process_password(message: types.Message, state: FSMContext):
    """Обработка пароля и авторизация"""
    user_id = message.from_user.id
    password_text = message.text.strip()
    data = await state.get_data()
    username = data.get('username')
    
    status_msg = await message.answer("⏳ Авторизация...")
    
    try:
        # Вызов сервиса авторизации
        token = await APIService.authenticate(username, password_text)
        
        user_tokens[user_id] = {
            'token': token,
            'username': username
        }
        
        await status_msg.delete()
        await message.answer(
            f"✅ Добро пожаловать, {username}!\n"
            "Выберите действие:",
            reply_markup=get_main_menu()
        )
        await state.set_state(AuthStates.in_menu)
        
    except Exception as e:
        error_msg = get_user_friendly_error(e)
        await status_msg.edit_text(error_msg)
        
        # Если ошибка авторизации - сбрасываем состояние
        if isinstance(e, (AuthenticationError, ValidationError)):
            await state.clear()


async def handle_menu(message: types.Message, state: FSMContext):
    """Обработка кнопок меню"""
    user_id = message.from_user.id
    
    # ✅ ДОБАВЛЕНО: Логирование для отладки
    logger.info(f"User {user_id} pressed button: {message.text}")
    logger.debug(f"Current state: {await state.get_state()}")
    
    if user_id not in user_tokens:
        await message.answer(
            "❌ Сессия истекла. Войдите снова: /start",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
        return
    
    text = message.text
    
    if text == "📤 Выгрузить Excel":
        await message.answer(
            "📎 Отправьте Excel файл (.xlsx или .xls)\n"
            "Я загружу его на сервер."
        )
        await state.set_state(AuthStates.waiting_file)
    
    elif text == "📊 Скачать Excel":
        await export_excel_handler(message, state)
    
    elif text == "🚪 Выход":
        if user_id in user_tokens:
            del user_tokens[user_id]
        await message.answer(
            "👋 До свидания! Для новой сессии: /start",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
    
    else:
        # ✅ ДОБАВЛЕНО: Обработка неизвестных команд
        logger.warning(f"Unknown command from user {user_id}: {text}")
        await message.answer(
            "❓ Неизвестная команда. Выберите действие из меню:",
            reply_markup=get_main_menu()
        )


async def export_excel_handler(message: types.Message, state: FSMContext):
    """Экспорт Excel файла"""
    user_id = message.from_user.id
    
    if user_id not in user_tokens:
        await message.answer("❌ Сессия истекла: /start")
        return
    
    token = user_tokens[user_id]['token']
    status_msg = await message.answer("⏳ Генерирую Excel файл...")
    
    try:
        # Вызов сервиса экспорта
        file_data, filename = await APIService.export_excel(token)
        
        await status_msg.delete()
        
        # Отправка файла
        file = types.BufferedInputFile(file_data, filename=filename)
        await message.answer_document(
            document=file,
            caption="✅ Ваш Excel файл готов!"
        )
        
    except AuthenticationError:
        # Токен истёк - удаляем из хранилища
        if user_id in user_tokens:
            del user_tokens[user_id]
        error_msg = get_user_friendly_error(AuthenticationError("Токен истёк"))
        await status_msg.edit_text(error_msg)
        await state.clear()
        
    except Exception as e:
        error_msg = get_user_friendly_error(e)
        await status_msg.edit_text(error_msg)


async def handle_file(message: types.Message, state: FSMContext):
    """Обработка загруженного файла"""
    user_id = message.from_user.id
    
    if user_id not in user_tokens:
        await message.answer("❌ Сессия истекла: /start")
        await state.clear()
        return
    
    if not message.document:
        # ✅ ДОБАВЛЕНО: Если пользователь отправил текст вместо файла
        await message.answer(
            "❌ Пожалуйста, отправьте файл или попросите еще раз:",
            reply_markup=get_main_menu()
        )
        await state.set_state(AuthStates.in_menu)
        return
    
    file_name = message.document.file_name
    token = user_tokens[user_id]['token']
    status_msg = await message.answer("⏳ Загружаю файл на сервер...")
    
    try:
        # Скачиваем файл
        file = await message.bot.get_file(message.document.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        file_data = file_bytes.read()
        
        # Вызов сервиса загрузки
        result = await APIService.upload_excel(token, file_data, file_name)
        
        await status_msg.edit_text(
            f"✅ Файл успешно загружен!\n\n"
            f"📄 Файл: {file_name}\n\n"
            "Выберите действие:",
        )
        # ✅ ИСПРАВЛЕНО: Возвращаем меню и устанавливаем состояние
        await message.answer(
            "Что хотите сделать дальше?",
            reply_markup=get_main_menu()
        )
        await state.set_state(AuthStates.in_menu)
        
    except AuthenticationError:
        # Токен истёк - удаляем из хранилища
        if user_id in user_tokens:
            del user_tokens[user_id]
        error_msg = get_user_friendly_error(AuthenticationError("Токен истёк"))
        await status_msg.edit_text(error_msg)
        await state.clear()
        
    except Exception as e:
        error_msg = get_user_friendly_error(e)
        await status_msg.edit_text(error_msg)
        # ✅ ИСПРАВЛЕНО: Возвращаем меню даже при ошибке
        await message.answer(
            "Попробуйте снова:",
            reply_markup=get_main_menu()
        )
        await state.set_state(AuthStates.in_menu)


async def main():
    """Запуск бота"""
    # ✅ ИСПРАВЛЕНО: Инициализация логирования
    config.setup_logging()
    
    bot = Bot(token=config.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрация handlers
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(process_login, AuthStates.waiting_email)
    dp.message.register(process_password, AuthStates.waiting_password)
    dp.message.register(handle_file, AuthStates.waiting_file, F.document)
    # ✅ ДОБАВЛЕНО: Обработка текста в состоянии waiting_file
    dp.message.register(handle_file, AuthStates.waiting_file)
    dp.message.register(handle_menu, AuthStates.in_menu)
    
    # Запуск
    logger.info("🚀 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt):
        print("Bot stopped")
    