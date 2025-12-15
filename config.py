import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logging(log_level: str = "INFO", log_to_file: bool = True, log_dir: str = "logs"):
    """
    Настройка логирования для бота
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Сохранять ли логи в файл
        log_dir: Директория для хранения логов
    """
    # Создаем директорию для логов, если её нет
    if log_to_file and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Формат логов
    log_format = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Получаем root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Очищаем существующие handlers
    root_logger.handlers.clear()
    
    # Console handler (вывод в консоль)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    if log_to_file:
        # Общий файл логов (с ротацией)
        general_log_file = os.path.join(log_dir, "bot.log")
        file_handler = RotatingFileHandler(
            general_log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(log_format)
        root_logger.addHandler(file_handler)
        
        # Файл для ошибок
        error_log_file = os.path.join(log_dir, "errors.log")
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(log_format)
        root_logger.addHandler(error_handler)
        
        # Дневной лог (новый файл каждый день)
        today = datetime.now().strftime("%Y-%m-%d")
        daily_log_file = os.path.join(log_dir, f"bot_{today}.log")
        daily_handler = logging.FileHandler(
            daily_log_file,
            encoding='utf-8'
        )
        daily_handler.setLevel(logging.DEBUG)
        daily_handler.setFormatter(log_format)
        root_logger.addHandler(daily_handler)
    
    # Настройка логирования для сторонних библиотек
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    
    logging.info("=" * 50)
    logging.info("Логирование настроено")
    logging.info(f"Уровень: {log_level}")
    logging.info(f"Логи в файл: {log_to_file}")
    if log_to_file:
        logging.info(f"Директория логов: {log_dir}")
    logging.info("=" * 50)


# Конфигурация API
class Config:
    """Класс для хранения конфигурации приложения"""
    
    def __init__(self):
        from dotenv import load_dotenv
        load_dotenv()
        
        # Telegram Bot
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        
        # API endpoints
        self.API_BASE_URL = os.getenv("API_BASE_URL")
        self.LOGIN_ENDPOINT = os.getenv("LOGIN_ENDPOINT")
        self.EXPORT_EXCEL_ENDPOINT = os.getenv("EXPORT_EXCEL_ENDPOINT")
        self.UPLOAD_ENDPOINT = os.getenv("UPLOAD_ENDPOINT")
        
        # Настройки логирования
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
        self.LOG_DIR = os.getenv("LOG_DIR", "logs")
        
        # Валидация обязательных параметров
        self._validate()
    
    def _validate(self):
        """Проверка наличия обязательных параметров"""
        required_params = {
            "BOT_TOKEN": self.BOT_TOKEN,
            "API_BASE_URL": self.API_BASE_URL,
            "LOGIN_ENDPOINT": self.LOGIN_ENDPOINT,
            "EXPORT_EXCEL_ENDPOINT": self.EXPORT_EXCEL_ENDPOINT,
            "UPLOAD_ENDPOINT": self.UPLOAD_ENDPOINT,
        }
        
        missing = [key for key, value in required_params.items() if not value]
        
        if missing:
            raise ValueError(
                f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}\n"
                "Проверьте файл .env"
            )
    
    def setup_logging(self):
        """Инициализация логирования"""
        setup_logging(
            log_level=self.LOG_LEVEL,
            log_to_file=self.LOG_TO_FILE,
            log_dir=self.LOG_DIR
        )


# Создаем глобальный экземпляр конфигурации
try:
    config = Config()
except ValueError as e:
    # Если не удалось загрузить конфигурацию, выводим ошибку и выходим
    print(f"❌ Ошибка конфигурации: {e}")
    import sys
    sys.exit(1)