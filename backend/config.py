# backend/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    razorpay_key_id: str
    razorpay_key_secret: str
    razorpay_webhook_secret: str
    database_url: str
    redis_url: str = "redis://localhost:6379"
    anthropic_api_key: str
    environment: str = "development"
    admin_secret: str

    # Episode timing
    provisional_wait_seconds: int = 300   # 5 min wait before final_failed
    max_recovery_attempts: int = 2
    max_recovery_amount_paise: int = 100000  # Rs.1000 cap
    quiet_hours_start: int = 22             # 10pm
    quiet_hours_end: int = 8               # 8am

    class Config:
        env_file = "../.env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()