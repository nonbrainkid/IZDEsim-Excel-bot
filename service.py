import aiohttp
from typing import Optional, Tuple
import logging
from validators import (
    validate_login_response,
    validate_export_response,
    validate_upload_response,
    validate_file_extension,
    NetworkError,
    ValidationError
)
import os
from dotenv import load_dotenv


load_dotenv()  # Загружаем переменные окружения из .env файла
logger = logging.getLogger(__name__)

# API конфигурация
API_BASE_URL = os.getenv("API_BASE_URL")
LOGIN_ENDPOINT = os.getenv("LOGIN_ENDPOINT")
EXPORT_EXCEL_ENDPOINT = os.getenv("EXPORT_EXCEL_ENDPOINT")
UPLOAD_ENDPOINT = os.getenv("UPLOAD_ENDPOINT")


class APIService:
    """Сервис для работы с API"""
    
    @staticmethod
    def _get_headers(token: Optional[str] = None) -> dict:
        """Получение заголовков для запроса"""
        headers = {
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': 'true'
        }
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers
    
    @staticmethod
    async def authenticate(email: str, password: str) -> str:
        """
        Авторизация пользователя
        
        Args:
            username: Логин
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
                    LOGIN_ENDPOINT,
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
    async def export_excel(token: str) -> Tuple[bytes, str]:
        """
        Экспорт Excel файла
        
        Args:
            token: Токен авторизации
            
        Returns:
            Tuple[bytes, str]: (данные файла, имя файла)
            
        Raises:
            AuthenticationError: При ошибке авторизации
            NetworkError: При ошибке сети
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    EXPORT_EXCEL_ENDPOINT,
                    headers=APIService._get_headers(token)
                ) as response:
                    logger.info(f"Export request - Status: {response.status}, URL: {EXPORT_EXCEL_ENDPOINT}")
                    print(f"[EXPORT] Status: {response.status}")
                    
                    # Если ошибка, выводим детали
                    if response.status != 200:
                        try:
                            error_data = await response.json()
                            error_detail = error_data.get('detail') or error_data.get('error') or str(error_data)
                        except:
                            error_detail = await response.text()
                        
                        logger.error(f"Export failed - Status: {response.status}, Detail: {error_detail}")
                        print(f"[EXPORT] ❌ Error detail: {error_detail}")
                    
                    validate_export_response(response.status)
                    
                    # Получаем данные файла
                    file_data = await response.read()
                    
                    # Извлекаем имя файла из заголовков
                    content_disp = response.headers.get('Content-Disposition', '')
                    filename = 'export.xlsx'
                    
                    if 'filename=' in content_disp:
                        filename = content_disp.split('filename=')[-1].strip('"\'')
                    
                    logger.info(f"Excel exported successfully: {filename}, Size: {len(file_data)} bytes")
                    print(f"[EXPORT] ✅ Success: {filename}, {len(file_data)} bytes")
                    return file_data, filename
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error during export: {e}")
            print(f"[EXPORT] ❌ Network error: {type(e).__name__}: {e}")
            raise NetworkError("Не удалось подключиться к серверу")
        except Exception as e:
            logger.error(f"Unexpected error during export: {type(e).__name__}: {e}")
            print(f"[EXPORT] ❌ Unexpected error: {type(e).__name__}: {e}")
            raise
    
    @staticmethod
    async def upload_excel(token: str, file_data: bytes, filename: str) -> dict:
        """
        Загрузка Excel файла
        
        Args:
            token: Токен авторизации
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
        
        try:
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
                    'ngrok-skip-browser-warning': 'true'
                }
                
                async with session.post(
                    UPLOAD_ENDPOINT,
                    data=form_data,
                    headers=headers
                ) as response:
                    logger.info(f"Upload request - Status: {response.status}, File: {filename}, Size: {len(file_data)} bytes")
                    print(f"[UPLOAD] Status: {response.status}, File: {filename}")
                    
                    data = await response.json() if response.content_type == 'application/json' else {}
                    logger.info(f"Upload response: {data}")
                    print(f"[UPLOAD] Response: {data}")
                    
                    # Если ошибка, выводим детали
                    if response.status not in [200, 201]:
                        error_detail = data.get('detail') or data.get('error') or data.get('message') or str(data)
                        logger.error(f"Upload failed - Status: {response.status}, Detail: {error_detail}")
                        print(f"[UPLOAD] ❌ Error detail: {error_detail}")
                    else:
                        print(f"[UPLOAD] ✅ Success")
                    
                    result = validate_upload_response(response.status, data)
                    logger.info(f"File uploaded successfully: {filename}")
                    return result
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error during upload: {e}")
            print(f"[UPLOAD] ❌ Network error: {type(e).__name__}: {e}")
            raise NetworkError("Не удалось подключиться к серверу")
        except Exception as e:
            logger.error(f"Unexpected error during upload: {type(e).__name__}: {e}")
            print(f"[UPLOAD] ❌ Unexpected error: {type(e).__name__}: {e}")
            raise
