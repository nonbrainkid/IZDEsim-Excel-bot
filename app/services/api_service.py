import aiohttp
from typing import Optional, Tuple
import logging
from datetime import datetime, timedelta
from app.validators import (
    validate_login_response,
    validate_export_response,
    validate_upload_response,
    validate_file_extension,
    NetworkError,
    ValidationError,
    AuthenticationError
)
from app.config import config

logger = logging.getLogger(__name__)


class APIService:
    """Сервис для работы с API"""
    
    # Кэш токена для автоматической авторизации
    _cached_token: Optional[str] = None
    _token_expires_at: Optional[datetime] = None
    
    @staticmethod
    def _get_headers(token: Optional[str] = None) -> dict:
        """Получение заголовков для запроса"""
        headers = {
            'Content-Type': 'application/json',
        }
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers
    
    @staticmethod
    async def _get_or_refresh_token(force_refresh: bool = False) -> str:
        """
        Получение или обновление токена авторизации
        
        Args:
            force_refresh: Принудительно обновить токен
        
        Returns:
            str: Токен авторизации
            
        Raises:
            AuthenticationError: При ошибке авторизации
            NetworkError: При ошибке сети
        """
        # Проверяем, нужно ли обновлять токен
        now = datetime.now()
        
        # Если токен есть и не истек и не требуется принудительное обновление
        if (not force_refresh and 
            APIService._cached_token and 
            APIService._token_expires_at and 
            now < APIService._token_expires_at):
            logger.debug("Using cached token")
            return APIService._cached_token
        
        # Получаем новый токен
        if force_refresh:
            logger.info("Force refreshing token...")
        else:
            logger.info("Authenticating with IzdeSim backend...")
        
        try:
            token = await APIService.authenticate(
                config.IZDESIM_EMAIL,
                config.IZDESIM_PASSWORD
            )
            
            APIService._cached_token = token
            # TTL access-токена на бэкенде = 10 мин. Кэшируем на 8, чтобы не ловить
            # 401 на самой границе срока (подтверждено контрактом IzdeSim, Session 003).
            APIService._token_expires_at = now + timedelta(minutes=8)
            
            logger.info(f"Backend authentication successful, token cached until {APIService._token_expires_at}")
            
            return token
            
        except Exception as e:
            # Сбрасываем кэш при ошибке
            APIService._cached_token = None
            APIService._token_expires_at = None
            raise
    
    @staticmethod
    async def authenticate(email: str, password: str) -> str:
        """
        Авторизация пользователя
        
        Args:
            email: Email
            password: Пароль
            
        Returns:
            str: Токен авторизации
            
        Raises:
            AuthenticationError: При ошибке авторизации
            NetworkError: При ошибке сети
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    config.LOGIN_ENDPOINT,
                    json={
                        "email": email,
                        "password": password
                    },
                    headers=APIService._get_headers()
                ) as response:
                    data = await response.json()
                    token = validate_login_response(response.status, data)
                    logger.info(f"User {email} authenticated successfully")
                    return token
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error during authentication: {e}")
            raise NetworkError("Не удалось подключиться к серверу")
    
    @staticmethod
    async def _make_request_with_retry(request_func, operation_name: str):
        """
        Выполнение запроса с автоматическим повтором при истечении токена
        
        Args:
            request_func: Функция для выполнения запроса (принимает token)
            operation_name: Название операции для логирования
            
        Returns:
            Результат request_func
        """
        # Получаем токен
        token = await APIService._get_or_refresh_token()
        
        try:
            # Пытаемся выполнить запрос
            result = await request_func(token)
            return result
            
        except AuthenticationError as e:
            # Если токен истек (401), обновляем и повторяем
            if e.status_code == 401:
                logger.info(f"Token expired during {operation_name}, refreshing and retrying...")
                
                # Принудительно обновляем токен
                token = await APIService._get_or_refresh_token(force_refresh=True)
                
                # Повторяем запрос с новым токеном
                result = await request_func(token)
                logger.info(f"{operation_name} succeeded after token refresh")
                return result
            else:
                # Другая ошибка авторизации
                raise
    
    @staticmethod
    async def export_excel() -> Tuple[bytes, str]:
        """
        Экспорт Excel файла (с автоматической авторизацией)
        
        Returns:
            Tuple[bytes, str]: (данные файла, имя файла)
            
        Raises:
            AuthenticationError: При ошибке авторизации
            NetworkError: При ошибке сети
        """
        async def _do_export(token: str) -> Tuple[bytes, str]:
            """Внутренняя функция для выполнения экспорта"""
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    config.EXPORT_EXCEL_ENDPOINT,
                    headers=APIService._get_headers(token)
                ) as response:
                    logger.info(f"Export request - Status: {response.status}")
                    
                    # Валидация ответа (здесь может быть выброшен AuthenticationError)
                    validate_export_response(response.status)
                    
                    # Получаем данные файла
                    file_data = await response.read()
                    
                    # Извлекаем имя файла из заголовков
                    content_disp = response.headers.get('Content-Disposition', '')
                    filename = 'export.xlsx'
                    
                    if 'filename=' in content_disp:
                        filename = content_disp.split('filename=')[-1].strip('"\'')
                    
                    logger.info(f"Excel exported successfully: {filename}, Size: {len(file_data)} bytes")
                    return file_data, filename
        
        try:
            return await APIService._make_request_with_retry(_do_export, "export")
        except aiohttp.ClientError as e:
            logger.error(f"Network error during export: {e}")
            raise NetworkError("Не удалось подключиться к серверу")
    
    @staticmethod
    async def upload_excel(file_data: bytes, filename: str) -> dict:
        """
        Загрузка Excel файла (с автоматической авторизацией)
        
        Args:
            file_data: Данные файла
            filename: Имя файла
            
        Returns:
            dict: Ответ сервера
            
        Raises:
            AuthenticationError: При ошибке авторизации
            ValidationError: При ошибке валидации
            NetworkError: При ошибке сети
        """
        if not validate_file_extension(filename):
            raise ValidationError("Неподдерживаемый формат файла. Используйте .xlsx или .xls")
        
        async def _do_upload(token: str) -> dict:
            """Внутренняя функция для выполнения загрузки"""
            async with aiohttp.ClientSession() as session:
                form_data = aiohttp.FormData()
                form_data.add_field(
                    'file',
                    file_data,
                    filename=filename,
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                
                headers = {
                    'Authorization': f'Bearer {token}',
                }
                
                async with session.post(
                    config.UPLOAD_ENDPOINT,
                    data=form_data,
                    headers=headers
                ) as response:
                    logger.info(f"Upload request - Status: {response.status}, File: {filename}")
                    
                    data = await response.json() if response.content_type == 'application/json' else {}
                    
                    # Валидация ответа (здесь может быть выброшен AuthenticationError)
                    result = validate_upload_response(response.status, data)
                    
                    logger.info(f"File uploaded successfully: {filename}")
                    return result
        
        try:
            return await APIService._make_request_with_retry(_do_upload, "upload")
        except aiohttp.ClientError as e:
            logger.error(f"Network error during upload: {e}")
            raise NetworkError("Не удалось подключиться к серверу")