from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Ignore extra environment variables that aren't defined in the model
    )
    # Database
    DATABASE_URL: str
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    # For development: use "*" to allow all origins, or specify comma-separated list
    # For production: specify exact origins (e.g., "https://yourdomain.com,https://www.yourdomain.com")
    CORS_ORIGINS: str = "*"  # Allows all origins in development
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    
    # Social Media APIs
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    INSTAGRAM_CLIENT_ID: str = ""
    INSTAGRAM_CLIENT_SECRET: str = ""
    
    # AI Service
    AI_PROVIDER: str = "openai"  # openai, anthropic, or empty for mock
    AI_API_KEY: str = ""
    AI_API_URL: str = "https://api.openai.com/v1"
    
    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins. Returns ["*"] if CORS_ORIGINS is "*", otherwise returns list of origins."""
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
