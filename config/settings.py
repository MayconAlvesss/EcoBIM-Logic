from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # --- API Security ---
    # Set this in your .env file or as an environment variable before deploying.
    AURA_GLOBAL_API_KEY: str = "aura-dev-key-super-secret"

    # --- Carbon Thresholds ---
    # Elements with embodied carbon above this value (kgCO2e) are flagged as "Warning".
    AURA_CARBON_THRESHOLD_KG: float = 500.0

    # --- CORS ---
    # Comma-separated list of allowed origins for the web dashboard.
    AURA_ALLOWED_ORIGINS: str = "http://localhost:5500,http://localhost:3000,http://localhost:8080"

    # --- Database ---
    AURA_DB_PATH: str = ""  # Resolved at runtime in main.py if empty.

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.AURA_ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Singleton instance used throughout the application.
settings = Settings()
