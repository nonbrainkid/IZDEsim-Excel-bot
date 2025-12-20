import os
from typing import List

from app.logging import setup_logging

class Config:    
    def __init__(self):
        from dotenv import load_dotenv
        load_dotenv()
        
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        
        # API endpoints
        self.API_BASE_URL = os.getenv("API_BASE_URL")
        self.LOGIN_ENDPOINT = f"{self.API_BASE_URL}/users/login/"
        self.EXPORT_EXCEL_ENDPOINT = f"{self.API_BASE_URL}/coverage/export_excel/"
        self.UPLOAD_ENDPOINT = f"{self.API_BASE_URL}/coverage/upload_excel/"
        
        # Allowed emails for using bot
        self.ALLOWED_EMAILS = self._parse_allowed_emails()
        
        # For authenticate in IzdeSim backend
        self.IZDESIM_EMAIL = os.getenv("IZDESIM_EMAIL")
        self.IZDESIM_PASSWORD = os.getenv("IZDESIM_PASSWORD")
        
        self.SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
        self.SMTP_EMAIL = os.getenv("SMTP_EMAIL")
        self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
        
        # Settings for verification code
        self.VERIFICATION_CODE_LENGTH = 6  # Длина кода
        self.VERIFICATION_CODE_EXPIRY = 600  # Срок действия кода в секундах (5 минут)
        
        # Logging
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
        self.LOG_DIR = os.getenv("LOG_DIR", "logs")
        
        # Validate required parameters for starting
        self._validate()
    
    def _parse_allowed_emails(self) -> List[str]:
        emails_str = os.getenv("ALLOWED_EMAILS", "")
        if not emails_str:
            return []
        
        # format ALLOWED_EMAILS=email1@example.com,email2@example.com
        emails = [email.strip().lower() for email in emails_str.split(",")]
        emails = [email for email in emails if email]
        
        return emails
    
    def is_email_allowed(self, email: str) -> bool:
        return email.strip().lower() in self.ALLOWED_EMAILS
    
    def _validate(self):
        required_params = {
            "BOT_TOKEN": self.BOT_TOKEN,
            "API_BASE_URL": self.API_BASE_URL,
            "IZDESIM_EMAIL": self.IZDESIM_EMAIL,
            "IZDESIM_PASSWORD": self.IZDESIM_PASSWORD,
            "SMTP_EMAIL": self.SMTP_EMAIL,
            "SMTP_PASSWORD": self.SMTP_PASSWORD,
        }
        
        missing = [key for key, value in required_params.items() if not value]
        
        if missing:
            raise ValueError(
                f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}\n"
                "Проверьте файл .env"
            )
        
        if not self.ALLOWED_EMAILS:
            raise ValueError(
                "Список разрешенных email (ALLOWED_EMAILS) пуст или не указан в .env\n"
                "Добавьте хотя бы один email в формате: ALLOWED_EMAILS=email1@example.com,email2@example.com"
            )
    
    def setup_logging(self):
        setup_logging(
            log_level=self.LOG_LEVEL,
            log_to_file=self.LOG_TO_FILE,
            log_dir=self.LOG_DIR
        )


try:
    config = Config()
except ValueError as e:
    # Если не удалось загрузить конфигурацию, выводим ошибку и выходим
    print(f"❌ Ошибка конфигурации: {e}")
    import sys
    sys.exit(1)