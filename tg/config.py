"""Configuration: environment variables, constants, tier definitions."""

import os
import logging

from shared.tg.redact import RedactingFormatter

TG_KEY_ID = "telegram"


def bot_token() -> str:
    """The bot token from the host key vault, else CRYPTOGAMES_TG_TOKEN; never logged."""
    try:
        from shared.core.vault import vault_secret
    except ImportError:
        return os.environ.get("CRYPTOGAMES_TG_TOKEN", "")
    token = vault_secret("cryptogames", TG_KEY_ID, "telegram", log=logging.getLogger("cryptogames"))
    return token or os.environ.get("CRYPTOGAMES_TG_TOKEN", "")


# ── Environment ──────────────────────────────────────────
APP_ENV    = os.environ.get("APP_ENV", "production")
BOT_TOKEN  = bot_token()
DATA_DIR   = os.environ.get("CRYPTOGAMES_TG_DATA", os.path.expanduser("~/.cryptogames_tg"))
API_BASE   = os.environ.get("CRYPTOGAMES_API_BASE", "https://api.crypto.games")
WEB_URL    = os.environ.get("CRYPTOGAMES_WEB_URL", "")          # e.g. http://IP:8003
WEB_SECRET = os.environ.get("CRYPTOGAMES_WEB_SECRET_KEY", "")   # must match web app

# ── Rate limit tiers: seconds between bets ───────────────
TIERS = {
    "free":  1.0,    # 1 bet/sec
    "trial": 0.0,    # max speed
}

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
_root = logging.getLogger()
for _handler in _root.handlers:
    _handler.setFormatter(RedactingFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logger = logging.getLogger("cryptogames")

# Suppress noisy httpx request logs (Telegram polling etc)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ── Supported currencies ─────────────────────────────────
CURRENCIES = [
    "btc", "eth", "usdt", "xrp", "bnb", "sol", "usdc", "doge",
    "shib", "ltc", "bch", "pepe", "etc", "pol", "play",
]

# ── Config keys persisted per user ───────────────────────
CONFIG_KEYS = [
    "api_key", "currency", "rule", "multiplier",
    "base_bet", "strategy", "strategy_key", "win_mult", "loss_mult",
    "bet_delay", "max_profit", "max_loss", "max_bets", "max_wins",
    "stop_on_balance", "custom_rules_text", "delay_martin_threshold",
    "milestone_bets", "milestone_wins", "milestone_losses", "milestone_profit",
    "profit_increment", "profit_threshold", "profit_increment_scope",
    "streak_delay_loss", "streak_delay_win", "streak_delay_bets",
    "streak_reset_losses", "streak_reset_delay",
    "proxy",
]


def get_user_tier(user_id: int) -> str:
    """Return rate-limit tier for a user. Extensible for paid tiers."""
    return "trial"
