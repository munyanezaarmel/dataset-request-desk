from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Each value can be overridden by an environment variable of the same
    # name in capitals (DATABASE_URL, JWT_SECRET, ...).
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/dataset_desk"
    jwt_secret: str = "dev-only-change-me"  # MUST be overridden in production
    access_token_minutes: int = 60
    bcrypt_rounds: int = 12  # tests lower this to run faster
    seed_dir: str = "/seed"

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        """Hosting providers hand out URLs starting with postgres:// or postgresql://.
        SQLAlchemy needs to be told which driver to use, so we add it."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value


settings = Settings()