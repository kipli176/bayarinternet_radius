from pydantic import BaseSettings

class Settings(BaseSettings):
    # DB_HOST: str = "postgres"
    DB_HOST: str = "192.168.137.165"
    DB_USER: str = "kipli_user"
    DB_PASSWORD: str = "kipli_password"
    DB_NAME: str = "bayarinternet"
    DB_PORT: int = 15432

    class Config:
        env_file = ".env"

settings = Settings()
