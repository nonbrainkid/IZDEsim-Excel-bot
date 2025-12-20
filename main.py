import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from app.handlers import cmd_start, handle_file, handle_menu, process_email, process_verification_code
from app.states import AuthStates
from app.config import config 

logger = logging.getLogger(__name__)

async def main():
    """Запуск бота"""
    # ✅ ИСПРАВЛЕНО: Инициализация логирования
    config.setup_logging()
    
    bot = Bot(token=config.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрация handlers
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(process_email, AuthStates.waiting_email)
    dp.message.register(process_verification_code, AuthStates.waiting_code)
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
    