from typing import Optional


class APIError(Exception):
    """Базовое исключение для ошибок API"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = str(message)
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
