from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Базовое исключение для ошибок API"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(APIError):
    """Ошибка авторизации"""
    pass


class ValidationError(APIError):
    """Ошибка валидации данных"""
    pass


class NetworkError(APIError):
    """Ошибка сети"""
    pass


class ServerError(APIError):
    """Ошибка сервера"""
    pass


def validate_login_response(status: int, data: Dict[str, Any]) -> str:
    """
    Валидация ответа от эндпоинта логина
    
    Args:
        status: HTTP статус код
        data: Данные ответа
        
    Returns:
        str: Токен авторизации
        
    Raises:
        AuthenticationError: При ошибке авторизации
        ValidationError: При невалидном ответе
    """
    if status == 401:
        raise AuthenticationError("Неверный логин или пароль", status_code=401)
    
    if status == 400:
        error_msg = data.get('detail') or data.get('error') or "Некорректные данные"
        raise ValidationError(error_msg, status_code=400)
    
    if status >= 500:
        raise ServerError(f"Ошибка сервера (код {status})", status_code=status)
    
    if status != 200:
        raise APIError(f"Неожиданный статус: {status}", status_code=status)
    
    # Ищем токен в разных возможных полях
    token = (
        data["data"]["access"]
    )
    
    if not token:
        logger.error(f"Token not found in response: {data}")
        raise ValidationError("Токен не найден в ответе сервера")
    
    return token


def validate_export_response(status: int) -> None:
    """
    Валидация ответа от эндпоинта экспорта
    
    Args:
        status: HTTP статус код
        
    Raises:
        AuthenticationError: При ошибке авторизации
        ServerError: При ошибке сервера
    """
    if status == 401:
        raise AuthenticationError("Токен истёк или невалиден", status_code=401)
    
    if status == 403:
        raise AuthenticationError("Недостаточно прав для экспорта", status_code=403)
    
    if status == 404:
        raise ValidationError("Данные для экспорта не найдены", status_code=404)
    
    if status >= 500:
        raise ServerError(f"Ошибка сервера при экспорте (код {status})", status_code=status)
    
    if status != 200:
        raise APIError(f"Ошибка экспорта (код {status})", status_code=status)


def validate_upload_response(status: int, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Валидация ответа от эндпоинта загрузки
    
    Args:
        status: HTTP статус код
        data: Данные ответа
        
    Returns:
        Dict: Данные об загруженном файле
        
    Raises:
        AuthenticationError: При ошибке авторизации
        ValidationError: При ошибке валидации
        ServerError: При ошибке сервера
    """
    if status == 401:
        raise AuthenticationError("Токен истёк или невалиден", status_code=401)
    
    if status == 400:
        error_msg = "Невалидный файл"
        if data:
            error_msg = data.get('detail') or data.get('error') or error_msg
        raise ValidationError(error_msg, status_code=400)
    
    if status == 413:
        raise ValidationError("Файл слишком большой", status_code=413)
    
    if status >= 500:
        raise ServerError(f"Ошибка сервера при загрузке (код {status})", status_code=status)
    
    if status not in [200, 201]:
        raise APIError(f"Ошибка загрузки (код {status})", status_code=status)
    
    return data or {}


def validate_file_extension(filename: str) -> bool:
    """
    Проверка расширения файла
    
    Args:
        filename: Имя файла
        
    Returns:
        bool: True если расширение валидно
    """
    return filename.lower().endswith(('.xlsx', '.xls'))


def get_user_friendly_error(error: Exception) -> str:
    """
    Преобразование исключения в понятное пользователю сообщение
    
    Args:
        error: Исключение
        
    Returns:
        str: Сообщение для пользователя
    """
    if isinstance(error, AuthenticationError):
        return f"❌ {error.message}\n\nВойдите заново: /start"
    
    if isinstance(error, ValidationError):
        return f"❌ {error.message}"
    
    if isinstance(error, NetworkError):
        return "❌ Ошибка подключения к серверу.\nПроверьте интернет-соединение."
    
    if isinstance(error, ServerError):
        return f"❌ {error.message}\n\nПопробуйте позже."
    
    if isinstance(error, APIError):
        return f"❌ {error.message}"
    
    # Неизвестная ошибка
    logger.error(f"Unexpected error: {type(error).__name__}: {error}")
    return "❌ Произошла непредвиденная ошибка.\nПопробуйте позже."

