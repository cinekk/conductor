from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    linear_api_key: str = ""
    linear_webhook_secret: str = ""
    linear_team_id: str = ""
    projects_file: str = "projects.yaml"
    log_level: str = "INFO"


settings = Settings()
