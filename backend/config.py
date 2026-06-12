"""Robin Backend — Configuration"""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b-instruct-q4_K_M"
    PIONEER_API_KEY: str = ""
    PIONEER_BASE_URL: str = "https://api.pioneer.ai/v1"
    PIONEER_MODEL: str = "meta-llama/Llama-3.1-8B-Instruct"
    PIONEER_SMART_MODEL: str = "claude-sonnet-4-6"
    GROQ_API_KEY: str = ""
    LLM_PROVIDER: str = "pioneer"  # "auto" | "ollama" | "groq" | "pioneer"

    # TrueFoundry
    TRUEFOUNDRY_API_KEY: str = ""
    TRUEFOUNDRY_WORKSPACE_FQN: str = ""

    # Guild AI
    GUILD_API_KEY: str = ""
    GUILD_PROJECT_ID: str = "robin"

    # Composio
    COMPOSIO_API_KEY: str = ""

    # ClickHouse
    CLICKHOUSE_HOST: str = ""
    CLICKHOUSE_PORT: int = 8443
    CLICKHOUSE_USER: str = "default"
    CLICKHOUSE_PASSWORD: str = ""
    CLICKHOUSE_DATABASE: str = "robin"

    # Airbyte (OAuth2 client credentials)
    AIRBYTE_CLIENT_ID: str = ""
    AIRBYTE_CLIENT_SECRET: str = ""
    AIRBYTE_ORGANIZATION_ID: str = ""
    AIRBYTE_CALENDAR_CONNECTION_ID: str = ""
    AIRBYTE_GMAIL_CONNECTION_ID: str = ""

    # App
    ROBIN_SECRET_KEY: str = "robin-secret"
    ENVIRONMENT: str = "development"

settings = Settings()
