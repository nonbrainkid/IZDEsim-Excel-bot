import random
import string
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Dict
from app.config import config

logger = logging.getLogger(__name__)


class VerificationStorage:
    """Хранилище кодов верификации"""
    
    def __init__(self):
        # Структура: {email: {"code": "123456", "expires_at": datetime, "attempts": 0}}
        self._storage: Dict[str, dict] = {}
    
    def save_code(self, email: str, code: str) -> None:
        """
        Сохранение кода верификации
        
        Args:
            email: Email адрес
            code: Код верификации
        """
        expires_at = datetime.now() + timedelta(seconds=config.VERIFICATION_CODE_EXPIRY)
        self._storage[email.lower()] = {
            "code": code,
            "expires_at": expires_at,
            "attempts": 0
        }
        logger.info(f"Verification code saved for {email}, expires at {expires_at}")
    
    def get_code(self, email: str) -> Optional[str]:
        """
        Получение кода верификации
        
        Args:
            email: Email адрес
            
        Returns:
            Optional[str]: Код верификации или None
        """
        data = self._storage.get(email.lower())
        if not data:
            return None
        
        # Проверка срока действия
        if datetime.now() > data["expires_at"]:
            logger.info(f"Verification code expired for {email}")
            self.delete_code(email)
            return None
        
        return data["code"]
    
    def verify_code(self, email: str, code: str) -> bool:
        """
        Проверка кода верификации
        
        Args:
            email: Email адрес
            code: Введенный код
            
        Returns:
            bool: True если код верный
        """
        data = self._storage.get(email.lower())
        if not data:
            logger.warning(f"No verification code found for {email}")
            return False
        
        # Проверка срока действия
        if datetime.now() > data["expires_at"]:
            logger.info(f"Verification code expired for {email}")
            self.delete_code(email)
            return False
        
        # Увеличиваем счетчик попыток
        data["attempts"] += 1
        
        # Проверка кода
        if data["code"] == code:
            logger.info(f"Verification successful for {email}")
            self.delete_code(email)  # Удаляем код после успешной верификации
            return True
        
        logger.warning(f"Invalid verification code for {email}, attempt {data['attempts']}")
        
        # Если слишком много попыток, удаляем код
        if data["attempts"] >= 3:
            logger.warning(f"Too many attempts for {email}, deleting code")
            self.delete_code(email)
        
        return False
    
    def delete_code(self, email: str) -> None:
        """
        Удаление кода верификации
        
        Args:
            email: Email адрес
        """
        if email.lower() in self._storage:
            del self._storage[email.lower()]
            logger.info(f"Verification code deleted for {email}")
    
    def cleanup_expired(self) -> None:
        """Очистка истекших кодов"""
        now = datetime.now()
        expired_emails = [
            email for email, data in self._storage.items()
            if now > data["expires_at"]
        ]
        
        for email in expired_emails:
            self.delete_code(email)
        
        if expired_emails:
            logger.info(f"Cleaned up {len(expired_emails)} expired codes")


class EmailService:
    """Сервис для работы с email верификацией"""
    
    @staticmethod
    def generate_code() -> str:
        """
        Генерация кода верификации
        
        Returns:
            str: Код верификации
        """
        return ''.join(random.choices(string.digits, k=config.VERIFICATION_CODE_LENGTH))
    
    @staticmethod
    async def send_verification_code(email: str, code: str) -> bool:
        """
        Отправка кода верификации на email
        
        Args:
            email: Email адрес получателя
            code: Код верификации
            
        Returns:
            bool: True если отправка успешна
        """
        try:
            # Создание сообщения
            msg = MIMEMultipart('alternative')
            msg['From'] = config.SMTP_EMAIL
            msg['To'] = email
            msg['Subject'] = "Код верификации IzdeSim Bot"
            
            # Текстовая версия письма
            text_body = f'''
                Здравствуйте!

                Ваш код верификации для доступа к IzdeSim Bot:

                {code}

                Код действителен в течение 5 минут.

                Если вы не запрашивали этот код, просто проигнорируйте это письмо.

                С уважением,
                IzdeSim Bot
            '''
            
            # HTML версия письма (более красивая)
            # путь к файлу
            html_file_path = "app/services/mail.html"

            # читаем содержимое
            with open(html_file_path, "r", encoding="utf-8") as f:
                html_template = f.read()
                html_body = html_template.format(code=code) 
            
            # Прикрепляем обе версии
            part1 = MIMEText(text_body, 'plain', 'utf-8')
            part2 = MIMEText(html_body, 'html', 'utf-8')
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Подключение к SMTP серверу и отправка
            logger.info(f"Connecting to SMTP server: {config.SMTP_SERVER}:{config.SMTP_PORT}")
            
            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
            
            logger.info(f"Logging in to SMTP as {config.SMTP_EMAIL}")
            server.login(config.SMTP_EMAIL, config.SMTP_PASSWORD)
            
            logger.info(f"Sending email to {email}")
            server.send_message(msg)
            server.quit()
            
            logger.info(f"✅ Verification code sent successfully to {email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication failed: {e}")
            logger.error("Проверьте SMTP_EMAIL и SMTP_PASSWORD в .env")
            return False
            
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error while sending email to {email}: {e}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error while sending email to {email}: {type(e).__name__}: {e}")
            return False


# Глобальный экземпляр хранилища
verification_storage = VerificationStorage()