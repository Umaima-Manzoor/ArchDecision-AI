import logging
from pydantic_settings import BaseSettings      # automatically reads from .env file and environment variables and validates the values

logger = logging.getLogger(__name__)


class Settings(BaseSettings):           # Application configuration loaded from environment variables

    nebius_api_key: str = ""        # pydantic gives error for str = None
    tavily_api_key: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    nebius_model: str = "Qwen/Qwen3-235B-A22B-Instruct-2507"
    nebius_fallback_model: str = "google/gemma-3-27b-it"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}       # tells pydantic to load environment variables from .env file, otherwise BaseSettings will only read from the actual environment variables

    def validate_required_keys(self) -> None:   # Raise ValueError if required API keys are missing
        missing: list[str] = []
        if not self.nebius_api_key:
            missing.append("NEBIUS_API_KEY")
        if not self.tavily_api_key:
            missing.append("TAVILY_API_KEY")
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Copy .env.example to .env and fill in your keys."
            )
        logger.info("All required API keys loaded successfully")

    @property
    def langfuse_enabled(self) -> bool:     # Return True if Langfuse keys are configured
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


settings = Settings()