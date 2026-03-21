"""Application settings loaded from environment / .env file."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings

_env = os.getenv("APP_ENV", "production")
_env_file = ".env.testing" if _env == "testing" else ".env"


class Settings(BaseSettings):
    # ── App ──
    app_name: str = "CryptoGames Admin"
    app_env: str = _env
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8003

    # ── Auth ──
    secret_key: str = "change-me-to-a-random-64-char-string"
    admin_user: str = "admin"
    admin_pass: str = "changeme123"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    tg_token_expire_minutes: int = 5

    # ── Paths ──
    db_path: str = os.path.expanduser("~/.cryptogames_web.db")
    bot_data_dir: str = os.path.expanduser("~/.cryptogames_tg")
    install_dir: str = os.path.expanduser("~/cryptogames-bot")
    repo_dir: str = os.path.expanduser("~/cryptogames")

    # ── Services ──
    service_cli: str = "cryptogames"
    service_tg: str = "cryptogames-tg"
    service_web: str = "cryptogames-web"

    # ── Telegram ──
    tg_bot_token: str = ""

    model_config = {"env_prefix": "CRYPTOGAMES_WEB_", "env_file": _env_file, "extra": "ignore"}


settings = Settings()

# Resolved paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
