"""
Configuration settings for Z.AI Proxy
"""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Z.AI settings
    UPSTREAM_URL: str = "https://chat.z.ai/api/chat/completions"
    UPSTREAM_MODEL: str = "0727-360B-API"

    # Model settings (OpenAI SDK compatible)
    MODEL_NAME: str = "GLM-4.5"
    MODEL_ID: str = "GLM-4.5"

    # API Key for external authentication
    API_KEY: str = os.getenv("API_KEY", "sk-z2api-key-2024")

    # Content filtering settings (only applies to non-streaming responses)
    SHOW_THINK_TAGS: bool = os.getenv("SHOW_THINK_TAGS", "false").lower() in ("true", "1", "yes")

    # Response mode settings
    DEFAULT_STREAM: bool = os.getenv("DEFAULT_STREAM", "false").lower() in ("true", "1", "yes")

    # Cookie settings
    COOKIES: List[str] = []

    # Auto refresh settings
    AUTO_REFRESH_TOKENS: bool = os.getenv("AUTO_REFRESH_TOKENS", "false").lower() in ("true", "1", "yes")
    REFRESH_CHECK_INTERVAL: int = int(os.getenv("REFRESH_CHECK_INTERVAL", "3600"))  # 1 hour

    def __init__(self):
        # Load cookies from environment variable
        cookies_str = os.getenv("Z_AI_COOKIES", "")
        if cookies_str and cookies_str != "your_z_ai_cookie_here":
            self.COOKIES = [cookie.strip() for cookie in cookies_str.split(",") if cookie.strip()]

        # Don't raise error immediately, let the application handle it
        if not self.COOKIES:
            print("Warning: No valid Z.AI cookies configured!")
            print("Please set Z_AI_COOKIES environment variable with comma-separated cookie values.")
            print("Example: Z_AI_COOKIES=cookie1,cookie2,cookie3")
            print("The server will start but API calls will fail until cookies are configured.")

    # Rate limiting
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Create settings instance
try:
    settings = Settings()
except Exception as e:
    print(f"Configuration error: {e}")
    settings = None
