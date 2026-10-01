from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Read from the DATABASE_URL environment variable if it exists,
    # otherwise fall back to this default (handy for running outside Docker).
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/dataset_desk"


settings = Settings()