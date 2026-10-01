from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Each value can be overridden by an environment variable of the same
    # name in capitals (DATABASE_URL, JWT_SECRET, ...).
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/dataset_desk"
    jwt_secret: str = "dev-only-change-me"  # MUST be overridden in production
    access_token_minutes: int = 60
    bcrypt_rounds: int = 12  # tests lower this to run faster
    seed_dir: str = "/seed"


settings = Settings()