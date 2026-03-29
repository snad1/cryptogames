# CryptoGames AutoBot v1.0 + Telegram Bot v1.0.1

High-speed auto-betting engine for crypto.games Dice with a live dashboard, Telegram bot, and web admin panel. Runs on any server or local machine — leave it running and manage via CLI, Telegram, or browser.

---

## Architecture

```text
cryptogames/
├── cryptogames.py      CLI bot (TUI dashboard, wizard, monitor)
├── core/               Shared package (single source of truth)
│   ├── strategy.py     Strategies, rule engine, StrategyRule class
│   ├── database.py     DB schema, migrations, WAL connections
│   └── engine.py       Strategy computation, rule evaluation
├── tg/                 Telegram bot package
│   ├── bot.py          Entry point, command registration
│   ├── handlers.py     All /command handlers
│   ├── engine.py       Per-user BettingEngine (uses core/)
│   ├── database.py     Per-user DB/config paths
│   ├── formatter.py    Telegram message formatting
│   ├── config.py       Env-based configuration
│   └── strategy.py     Re-exports from core/
├── web/                FastAPI admin dashboard
│   ├── app.py          FastAPI factory
│   ├── auth.py         JWT auth, roles (admin/user)
│   ├── database.py     Web DB schema (users, audit log)
│   ├── bot_db.py       Bridge to bot SQLite
│   ├── services.py     Systemd service control
│   └── routes/         API, admin, user, auth, WebSocket routes
├── install.sh          Server installer (systemd, cgctl, venv)
├── .env.example        Environment variable template
└── requirements.txt    Python dependencies (includes casino-shared)
```

Both the CLI bot and Telegram bot import shared logic from `core/` — change once, applies everywhere. Cross-bot shared code (`shared/`) is installed as a pip package (`casino-shared`) from GitHub.

---

## Features

| Feature | Details |
|---|---|
| **Pure ANSI TUI** | Direct ANSI rendering, fits any terminal, refreshes 2x/sec |
| **Telegram bot** | Full control via Telegram — start/stop/pause/status/config |
| **Web dashboard** | FastAPI admin panel with JWT auth, CSV export, WebSocket live updates |
| **8 betting strategies** | Flat, Martingale, Anti-Martingale, D'Alembert, Paroli, CryptoRider, Delay Martingale, Rule-Based |
| **21 rule actions** | Full action set: bet amount, win chance, payout multiplier, switch, stop, reset |
| **15 currencies** | BTC, ETH, USDT, XRP, BNB, SOL, USDC, DOGE, SHIB, LTC, BCH, PEPE, ETC, POL, PLAY |
| **Named presets** | Save & load strategy configs by name |
| **Env-based config** | API key, paths, Telegram token — all via environment variables |
| **Secure file handling** | Config files written with 0600 permissions, API keys masked in logs |
| **Session database** | SQLite log of every bet and session — survives restarts |
| **Auto data retention** | Old bet records auto-purged after 3 days; session stats preserved forever |
| **Daemon + monitor** | `--daemon` for background, `--monitor` to attach live TUI |
| **Performance tracking** | BPS, BPM, peak/low speed, peak/low balance, best win, worst loss |
| **Base bet validation** | Validated against `MinBet` from API before session starts |
| **Benchmark command** | `/benchmark` to test API response speed |
| **Daily log rotation** | Logs at `~/.cryptogames_logs/`, rotates at midnight, 30-day retention |

---

## Quick Start

### Local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run wizard (guides you through config)
python3 cryptogames.py

# Get your API key from: https://crypto.games/settings
```

### Remote Server

```bash
# Upload files
scp -r cryptogames.py requirements.txt install.sh core/ tg/ .env.example user@your-server:~/cryptogames/

# Install (sets up venv, systemd, cgctl)
ssh user@your-server
cd ~/cryptogames && chmod +x install.sh && ./install.sh
```

### cgctl Management

```bash
cgctl setup             # Run wizard to configure
cgctl start             # Start CLI bot as daemon
cgctl stop              # Stop CLI bot
cgctl monitor           # Attach live TUI to running daemon
cgctl status            # Check running session status
cgctl stats             # Show all-time session statistics

cgctl tg env            # Edit .env (set Telegram token)
cgctl tg start          # Start Telegram bot
cgctl tg stop           # Stop Telegram bot
cgctl tg logs           # Stream Telegram bot logs

cgctl web install       # Install web dashboard
cgctl web start         # Start web dashboard
cgctl web stop          # Stop web dashboard
cgctl web logs          # Stream web dashboard logs

cgctl start-all         # Start all services
cgctl stop-all          # Stop all services
cgctl status-all        # Check all services
```

---

## Telegram Bot

The Telegram bot provides full betting control from your phone. Each Telegram user gets isolated storage (DB, config, presets).

### Setup

1. Open Telegram, search **@BotFather**, `/newbot`
2. Choose a name and username, copy the token
3. On your server: `cgctl tg env` and set `CRYPTOGAMES_TG_TOKEN=<token>`
4. `cgctl tg start`
5. Open your bot in Telegram and `/start`

### Commands

| Command | Description |
|---|---|
| `/start` | Welcome and quick start guide |
| `/help` | Full command reference |
| `/setkey` | Set crypto.games API key |
| `/balance` | Check balances |
| `/config` | View current config |
| `/set <param> <value>` | Set a parameter |
| `/strategies` | List available strategies |
| `/bet` | Start betting session (up to 5 concurrent) |
| `/stop [slot\|all]` | Stop session |
| `/pause [slot\|all]` / `/resume [slot\|all]` | Pause/resume betting |
| `/status [slot]` | Live status — summary when multiple sessions |
| `/monitor [slot] [interval]` | Auto-updating status (3-60s) |
| `/stats` | Session history |
| `/session <id>` | Full session report with config snapshot + streaks |
| `/lastbets [N]` | Recent bets |
| `/rules` | List current rules |
| `/addrule <JSON>` | Add a rule |
| `/delrule <N>` | Delete rule by number |
| `/editrule <N> <JSON>` | Edit rule by number (JSON patch) |
| `/clearrules` | Clear all rules |
| `/presets` | List presets |
| `/savepreset <name>` | Save current config |
| `/loadpreset <name>` | Load a preset |
| `/web` | Open web dashboard |
| `/benchmark` | Test API response speed |
| `/cleanup [days]` | Purge old bet records (default 3 days), keep session stats |
| `/delsession <id>` | Delete a specific session and its bets |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CRYPTOGAMES_API_KEY` | *(none)* | API key from crypto.games settings |
| `CRYPTOGAMES_API_BASE` | `https://api.crypto.games` | API base URL |
| `CRYPTOGAMES_DB_PATH` | `~/.cryptogames_autobot.db` | SQLite database path |
| `CRYPTOGAMES_CONFIG_PATH` | `~/.cryptogames_autobot.json` | Saved config path |
| `CRYPTOGAMES_LOG_DIR` | `~/.cryptogames_logs` | Log directory |
| `CRYPTOGAMES_TG_TOKEN` | *(none)* | Telegram bot token |
| `CRYPTOGAMES_TG_DATA` | `~/.cryptogames_tg` | Per-user Telegram data dir |
| `CRYPTOGAMES_WEB_SECRET_KEY` | *(none)* | JWT secret for web dashboard |

---

## Strategies

| Nr | Name | How it works | Risk |
|---|---|---|---|
| 1 | **Flat Bet** | Same amount every time | Very Low |
| 2 | **Martingale** | Multiply on loss, reset on win | High |
| 3 | **Anti-Martingale** | Multiply on win, reset on loss | Medium |
| 4 | **D'Alembert** | +1 unit on loss, -1 on win | Low-Medium |
| 5 | **Paroli (3-step)** | Multiply on win up to 3x then reset | Medium |
| 6 | **CryptoRider** | Multiply on loss + switch over/under on bet 2/6/9 | High |
| 7 | **Delay Martingale** | Flat for N losses, then multiply | High |
| 8 | **Rule-Based** | Custom IF/THEN conditions & actions | Variable |

---

## Rule-Based Strategy (Strategy 8)

### Condition Modes

| Mode | Behavior |
|---|---|
| **Every N** | Fires at every Nth total win/loss/bet |
| **Every streak of N** | Fires at N, 2N, 3N within a streak (modulus) |
| **First streak of N** | Fires once when streak first hits N (resets on flip) |
| **Streak above N** | Fires every bet past N in streak |
| **Streak below N** | Fires when streak is below N |

### Actions

**Bet Amount:** Reset, Increase by %, Decrease by %, Add fixed, Deduct fixed, Set exact
**Win Chance:** Reset, Set, Increase by %, Decrease by %, Add, Deduct
**Payout:** Reset, Set, Increase by %, Decrease by %, Add, Deduct
**Other:** Switch over/under, Stop, Reset game

---

## CLI Options

```bash
python3 cryptogames.py                   # Interactive wizard + TUI
python3 cryptogames.py --resume          # Skip wizard, reuse saved config
python3 cryptogames.py --preset X        # Load preset X and start
python3 cryptogames.py --daemon          # Background (no TUI, implies --resume)
python3 cryptogames.py --monitor         # Attach live TUI to running daemon
python3 cryptogames.py --status          # Check running session status
python3 cryptogames.py --stop            # Stop a running daemon
python3 cryptogames.py --setup-only      # Wizard only, don't start
python3 cryptogames.py --stats           # Session history + totals
python3 cryptogames.py --last-bets N     # Last N bets across sessions
python3 cryptogames.py --session-bets N  # Full stats + streaks for session N
python3 cryptogames.py --verbose         # Enable DEBUG logging
```

---

## API

| Endpoint | Purpose |
|---|---|
| `GET /v1/balance/{coin}/{api_key}` | Single coin balance |
| `GET /v1/BalanceAll/{api_key}` | All balances |
| `GET /v1/settings/{coin}` | Game settings (min/max bet) |
| `POST /v1/placebet/{coin}/{api_key}` | Place a Dice bet |

Base URL: `https://api.crypto.games`

Auth: API key passed in URL path.

---

## Disclaimer

This software is provided as-is for educational purposes. Gambling involves real financial risk. Never bet more than you can afford to lose. Use the stop conditions. Be responsible.
