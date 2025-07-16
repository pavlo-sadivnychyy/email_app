from pydantic_settings import BaseSettings
from typing import List
import json

class Settings(BaseSettings):
    # App
    APP_NAME: str = "AI Email Marketing Assistant"
    APP_URL: str = "http://localhost:3000"
    API_URL: str = "http://localhost:8000"
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/email_marketing_db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # JWT
    SECRET_KEY: str = "your-super-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID_STARTER: str = ""
    STRIPE_PRICE_ID_BUSINESS: str = ""
    STRIPE_PRICE_ID_PROFESSIONAL: str = ""
    STRIPE_PRICE_ID_ENTERPRISE: str = ""
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    
    # Email Service
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@example.com"
    
    # AWS
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "eu-central-1"
    S3_BUCKET_NAME: str = ""
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds
    
    # Email limits per plan
    STARTER_CONTACT_LIMIT: int = 1000
    BUSINESS_CONTACT_LIMIT: int = 5000
    PROFESSIONAL_CONTACT_LIMIT: int = 15000
    ENTERPRISE_CONTACT_LIMIT: int = 999999999  # Effectively unlimited
    
    # AI Settings
    AI_MODEL: str = "gpt-4-turbo-preview"
    AI_TEMPERATURE: float = 0.7
    AI_MAX_TOKENS: int = 1000
    
    class Config:
        env_file = ".env"
        extra = "allow"
        
    def get_stripe_price_id(self, plan: str) -> str:
        price_map = {
            "starter": self.STRIPE_PRICE_ID_STARTER,
            "business": self.STRIPE_PRICE_ID_BUSINESS,
            "professional": self.STRIPE_PRICE_ID_PROFESSIONAL,
            "enterprise": self.STRIPE_PRICE_ID_ENTERPRISE,
        }
        return price_map.get(plan, "")
    
    def get_contact_limit(self, plan: str) -> int:
        limit_map = {
            "starter": self.STARTER_CONTACT_LIMIT,
            "business": self.BUSINESS_CONTACT_LIMIT,
            "professional": self.PROFESSIONAL_CONTACT_LIMIT,
            "enterprise": self.ENTERPRISE_CONTACT_LIMIT,
        }
        return limit_map.get(plan, self.STARTER_CONTACT_LIMIT)

settings = Settings()