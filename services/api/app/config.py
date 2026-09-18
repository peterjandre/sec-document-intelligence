from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Populate os.environ so rag.pipeline (which uses os.getenv) sees the same keys.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    allowed_origins: str = Field(default="http://localhost:3000", alias="ALLOWED_ORIGINS")
    extractor_cli_path: str = Field(
        default="../extractor-csharp/bin/Release/net8.0/extractor",
        alias="EXTRACTOR_CLI_PATH",
    )
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")


settings = Settings()
