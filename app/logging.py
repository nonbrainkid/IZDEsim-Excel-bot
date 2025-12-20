import os
import logging

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

