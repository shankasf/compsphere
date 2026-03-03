from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@72.62.162.83:5432/compsphere"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ANTHROPIC_API_KEY: str = ""
    MAX_CONCURRENT_SESSIONS: int = 2
    CONTAINER_TTL_MINUTES: int = 30
    SANDBOX_IMAGE: str = "compshere-sandbox:latest"
    BROWSER_PROFILES_PATH: str = "/data/browser-profiles"
    DOCKER_HOST_IP: str = "localhost"

    class Config:
        env_file = ".env"


settings = Settings()
