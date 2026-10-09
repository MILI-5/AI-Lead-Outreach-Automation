from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = (
        "AI Lead Generation & Client Outreach Automation"
    )

    app_env: str = "development"

    debug: bool = True

    database_url: str = (
        "sqlite:///./lead_automation.db"
    )

    # Gemini
    google_api_key: str = ""

    # Google Custom Search
    google_search_api_key: str = ""
    google_search_engine_id: str = ""

    # Telegram
    telegram_bot_token: str = ""

    # Google Calendar
    google_calendar_credentials_file: str = ""

    default_timezone: str = "Asia/Kolkata"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()