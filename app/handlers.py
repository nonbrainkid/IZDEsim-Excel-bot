import logging
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
from app.keyboards import get_main_menu
from app.states import AuthStates
from app.validators import (
    get_user_friendly_error
)
from app.services import EmailService, verification_storage, APIService
from app.config import config

logger = logging.getLogger(__name__)

# Хранилище верифицированных пользователей
verified_users = set()  # Множество user_id верифицированных пользователей


async def cmd_start(message: types.Message, state: FSMContext):
    """Команда /start"""
    await state.clear()
    await message.answer(
        "👋 Привет! Я бот для работы с Excel файлами IzdeSim.\n\n"
        "Для начала работы введите вашу почту:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AuthStates.waiting_email)


async def process_email(message: types.Message, state: FSMContext):
    """Обработка email и отправка кода верификации"""
    email = message.text.strip().lower()
    user_id = message.from_user.id
    
    # Базовая валидация email
    if '@' not in email or '.' not in email:
        await message.answer(
            "❌ Некорректный формат email. Попробуйте снова:"
        )
        return
    
    # Проверка, разрешен ли этот email
    if not config.is_email_allowed(email):
        logger.warning(f"Unauthorized email attempt: {email} from user {user_id}")
        await message.answer(
            "❌ Этот email не имеет доступа к боту.\n\n"
            "Обратитесь к администратору для получения доступа."
        )
        await state.clear()
        return
    
    # Генерация и отправка кода
    code = EmailService.generate_code()
    verification_storage.save_code(email, code)
    
    status_msg = await message.answer("⏳ Отправляю код верификации...")
    
    success = await EmailService.send_verification_code(email, code)
    
    if success:
        await state.update_data(email=email)
        await status_msg.edit_text(
            f"✅ Код верификации отправлен на {email}\n\n"
            f"📧 Введите код из письма (действителен 5 минут):"
        )
        await state.set_state(AuthStates.waiting_code)
    else:
        await status_msg.edit_text(
            "❌ Не удалось отправить код.\n"
            "Попробуйте позже или обратитесь к администратору."
        )
        await state.clear()


async def process_verification_code(message: types.Message, state: FSMContext):
    """Обработка кода верификации"""
    code = message.text.strip()
    user_id = message.from_user.id
    data = await state.get_data()
    email = data.get('email')
    
    if not email:
        await message.answer("❌ Сессия истекла. Начните заново: /start")
        await state.clear()
        return
    
    # Проверка кода
    if verification_storage.verify_code(email, code):
        # Код верный - добавляем пользователя в верифицированные
        verified_users.add(user_id)
        
        await message.answer(
            f"✅ Верификация успешна!\n\n"
            f"Добро пожаловать! Выберите действие:",
            reply_markup=get_main_menu()
        )
        await state.set_state(AuthStates.in_menu)
        
        logger.info(f"User {user_id} ({email}) verified successfully")
    else:
        # Код неверный
        stored_code = verification_storage.get_code(email)
        
        if stored_code is None:
            # Код истек или превышено количество попыток
            await message.answer(
                "❌ Код верификации истек или превышено количество попыток.\n\n"
                "Запросите новый код: /start"
            )
            await state.clear()
        else:
            # Код неверный, но еще есть попытки
            await message.answer(
                "❌ Неверный код. Попробуйте снова:\n\n"
                "Осталось попыток: до 3"
            )


async def handle_menu(message: types.Message, state: FSMContext):
    """Обработка кнопок меню"""
    user_id = message.from_user.id
    
    logger.info(f"User {user_id} pressed button: {message.text}")
    logger.debug(f"Current state: {await state.get_state()}")
    
    # Проверка верификации
    if user_id not in verified_users:
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
            "Я загружу его на сервер IzdeSim."
        )
        await state.set_state(AuthStates.waiting_file)
    
    elif text == "📊 Скачать Excel":
        await export_excel_handler(message, state)
    
    elif text == "🚪 Выход":
        if user_id in verified_users:
            verified_users.remove(user_id)
        await message.answer(
            "👋 До свидания! Для новой сессии: /start",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
    
    else:
        logger.warning(f"Unknown command from user {user_id}: {text}")
        await message.answer(
            "❓ Неизвестная команда. Выберите действие из меню:",
            reply_markup=get_main_menu()
        )


async def export_excel_handler(message: types.Message, state: FSMContext):
    """Экспорт Excel файла (с автоматической авторизацией на backend)"""
    user_id = message.from_user.id
    
    if user_id not in verified_users:
        await message.answer("❌ Сессия истекла: /start")
        await state.clear()
        return
    
    status_msg = await message.answer("⏳ Генерирую Excel файл...")
    
    try:
        # APIService автоматически авторизуется на backend
        file_data, filename = await APIService.export_excel()
        
        await status_msg.delete()
        
        # Отправка файла
        file = types.BufferedInputFile(file_data, filename=filename)
        await message.answer_document(
            document=file,
            caption="✅ Ваш Excel файл готов!"
        )
        
        logger.info(f"User {user_id} exported Excel: {filename}")
        
    except Exception as e:
        error_msg = get_user_friendly_error(e)
        await status_msg.edit_text(error_msg)
        logger.error(f"Export failed for user {user_id}: {e}")


async def handle_file(message: types.Message, state: FSMContext):
    """Обработка загруженного файла (с автоматической авторизацией на backend)"""
    user_id = message.from_user.id
    
    if user_id not in verified_users:
        await message.answer("❌ Сессия истекла: /start")
        await state.clear()
        return
    
    if not message.document:
        await message.answer(
            "❌ Пожалуйста, отправьте файл или выберите действие из меню:",
            reply_markup=get_main_menu()
        )
        await state.set_state(AuthStates.in_menu)
        return
    
    file_name = message.document.file_name
    status_msg = await message.answer("⏳ Загружаю файл на сервер IzdeSim...")
    
    try:
        # Скачиваем файл
        file = await message.bot.get_file(message.document.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        file_data = file_bytes.read()
        
        # APIService автоматически авторизуется на backend
        result = await APIService.upload_excel(file_data, file_name)
        
        await status_msg.edit_text(
            f"✅ Файл успешно загружен на IzdeSim!\n\n"
            f"📄 Файл: {file_name}"
        )
        
        await message.answer(
            "Что хотите сделать дальше?",
            reply_markup=get_main_menu()
        )
        await state.set_state(AuthStates.in_menu)
        
        logger.info(f"User {user_id} uploaded file: {file_name}")
        
    except Exception as e:
        error_msg = get_user_friendly_error(e)
        await status_msg.edit_text(error_msg)
        
        await message.answer(
            "Попробуйте снова:",
            reply_markup=get_main_menu()
        )
        await state.set_state(AuthStates.in_menu)
        
        logger.error(f"Upload failed for user {user_id}: {e}")