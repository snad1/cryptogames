#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  CryptoGames AutoBot: Server Installer v1.1
#  Sets up: CLI bot + Telegram bot, venv, systemd, cgctl
# ─────────────────────────────────────────────────────────
set -euo pipefail

INSTALL_DIR="$HOME/cryptogames-bot"
SERVICE_NAME="cryptogames"
LANE_SERVICE_NAME="cryptogames-lane"
TG_SERVICE_NAME="cryptogames-tg"
SYSTEMD_DIR="$HOME/.config/systemd/user"
CGCTL="$HOME/.local/bin/cgctl"
ENV_FILE="$INSTALL_DIR/.env"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   CryptoGames AutoBot: Server Installer v1.1        ║"
echo "║   CLI Bot + Telegram Bot                              ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. System dependencies ─────────────────────────────
echo "[1/7] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    sqlite3 tmux curl

# ── 2. Bot directory ───────────────────────────────────
echo "[2/7] Setting up bot directory..."
mkdir -p "$INSTALL_DIR"
cp cryptogames.py   "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"

# Copy core/ shared package
mkdir -p "$INSTALL_DIR/core"
cp core/__init__.py  "$INSTALL_DIR/core/"
cp core/strategy.py  "$INSTALL_DIR/core/"
cp core/database.py  "$INSTALL_DIR/core/"
cp core/engine.py    "$INSTALL_DIR/core/"

# Copy tg/ Telegram bot package
mkdir -p "$INSTALL_DIR/tg"
cp tg/__init__.py   "$INSTALL_DIR/tg/"
cp tg/config.py     "$INSTALL_DIR/tg/"
cp tg/database.py   "$INSTALL_DIR/tg/"
cp tg/engine.py     "$INSTALL_DIR/tg/"
cp tg/formatter.py  "$INSTALL_DIR/tg/"
cp tg/handlers.py   "$INSTALL_DIR/tg/"
cp tg/bot.py        "$INSTALL_DIR/tg/"


# ── 3. Environment file ───────────────────────────────
echo "[3/7] Setting up environment..."
if [ ! -f "$ENV_FILE" ]; then
    if [ -f ".env" ]; then
        cp .env "$ENV_FILE"
        echo "   Copied .env to $ENV_FILE"
    elif [ -f ".env.example" ]; then
        cp .env.example "$ENV_FILE"
        echo "   Created $ENV_FILE from .env.example"
        echo "   ⚠ EDIT THIS FILE: nano $ENV_FILE"
    else
        cat > "$ENV_FILE" << 'ENVEOF'
# CryptoGames AutoBot: Environment
# Get your Telegram bot token from @BotFather
CRYPTOGAMES_TG_TOKEN=
CRYPTOGAMES_TG_DATA=~/.cryptogames_tg
ENVEOF
        echo "   Created $ENV_FILE"
        echo "   ⚠ EDIT THIS FILE: nano $ENV_FILE"
    fi
else
    echo "   $ENV_FILE already exists (kept)"
fi
chmod 600 "$ENV_FILE"

# ── 4. Python virtual environment ─────────────────────
echo "[4/7] Creating Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# ── 5. Systemd services ───────────────────────────────
echo "[5/7] Setting up systemd services..."
mkdir -p "$SYSTEMD_DIR"

# CLI bot service
cat > "$SYSTEMD_DIR/${SERVICE_NAME}.service" << SERVICEEOF
[Unit]
Description=CryptoGames AutoBot: Dice Auto-Betting Engine (CLI)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
Nice=-5
IOSchedulingClass=best-effort
IOSchedulingPriority=0
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python3 ${INSTALL_DIR}/cryptogames.py --resume --daemon
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

KillSignal=SIGTERM
TimeoutStopSec=15

Environment=HOME=${HOME}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-${ENV_FILE}

[Install]
WantedBy=default.target
SERVICEEOF

# Parallel lanes 2..N: same unit as lane 1 plus --lane %i (cgctl lanes N)
cat > "$SYSTEMD_DIR/${LANE_SERVICE_NAME}@.service" << LANESERVICEEOF
[Unit]
Description=CryptoGames AutoBot - parallel lane %i (CLI)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
Nice=-5
IOSchedulingClass=best-effort
IOSchedulingPriority=0
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python3 ${INSTALL_DIR}/cryptogames.py --resume --daemon --lane %i
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

KillSignal=SIGTERM
TimeoutStopSec=15

Environment=HOME=${HOME}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-${ENV_FILE}

[Install]
WantedBy=default.target
LANESERVICEEOF

# Telegram bot service
cat > "$SYSTEMD_DIR/${TG_SERVICE_NAME}.service" << TGSERVICEEOF
[Unit]
Description=CryptoGames AutoBot: Telegram Bot
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python3 -m tg.bot
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

KillSignal=SIGTERM
TimeoutStopSec=15

Environment=HOME=${HOME}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=${ENV_FILE}

[Install]
WantedBy=default.target
TGSERVICEEOF

# Watchdog: restart TG bot if heartbeat file is stale (catches stuck-but-alive)
cat > "$SYSTEMD_DIR/${TG_SERVICE_NAME}-watchdog.service" << WDSERVICEEOF
[Unit]
Description=CryptoGames Telegram Bot: Stall Watchdog
After=${TG_SERVICE_NAME}.service

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'f=/tmp/${TG_SERVICE_NAME}.heartbeat; if [ ! -f "\$f" ] || [ \$(( \$(date +%%s) - \$(stat -c %%Y "\$f") )) -gt 180 ]; then echo "Heartbeat stale, restarting ${TG_SERVICE_NAME}"; systemctl --user restart ${TG_SERVICE_NAME}.service; fi'
WDSERVICEEOF

cat > "$SYSTEMD_DIR/${TG_SERVICE_NAME}-watchdog.timer" << WDTIMEREOF
[Unit]
Description=CryptoGames Telegram Bot: Stall Watchdog Timer (every 2 min)

[Timer]
OnBootSec=3min
OnUnitActiveSec=2min
Unit=${TG_SERVICE_NAME}-watchdog.service

[Install]
WantedBy=timers.target
WDTIMEREOF

# Enable lingering so user services run after logout
sudo loginctl enable-linger "$(whoami)" 2>/dev/null || true

systemctl --user daemon-reload
# Boot-enable only (no --now): a bot stopped by hand stays stopped until the next boot.
systemctl --user enable ${SERVICE_NAME} 2>/dev/null || true
systemctl --user enable --now ${TG_SERVICE_NAME}-watchdog.timer 2>/dev/null || true
echo "   Services installed:"
echo "     ${SERVICE_NAME}.service     (CLI bot)"
echo "     ${LANE_SERVICE_NAME}@.service (parallel lanes 2..N)"
echo "     ${TG_SERVICE_NAME}.service  (Telegram bot)"

# ── 6. Management CLI ─────────────────────────────────
echo "[6/7] Creating cgctl management command..."
mkdir -p "$HOME/.local/bin"
install -m 0755 cgctl "$CGCTL"

# ── 7. Quick-run scripts ──────────────────────────────
echo "[7/7] Creating helper scripts..."

cat > "$INSTALL_DIR/run.sh" << 'EOF'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$DIR/venv/bin/python3" "$DIR/cryptogames.py" "$@"
EOF
chmod +x "$INSTALL_DIR/run.sh"

cat > "$INSTALL_DIR/run-tg.sh" << 'EOF'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -a; source "$DIR/.env" 2>/dev/null; set +a
cd "$DIR" && "$DIR/venv/bin/python3" -m tg.bot "$@"
EOF
chmod +x "$INSTALL_DIR/run-tg.sh"

# ── Done ──────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  Installation complete!"
echo "════════════════════════════════════════════════════════"
echo ""
echo "  PROJECT STRUCTURE:"
echo "    $INSTALL_DIR/"
echo "    ├── cryptogames.py       CLI bot (TUI dashboard)"
echo "    ├── core/                Bot-specific: strategy, DB, engine"
echo "    ├── tg/                  Telegram bot package"
echo "    ├── shared/              Cross-bot shared library"
echo "    ├── .env                 Environment config (tokens)"
echo "    └── venv/                Python virtual environment"
echo ""
echo "  ── STEP 1: CLI BOT SETUP ──"
echo "    cgctl setup              Configure API key, strategy"
echo "    cgctl start              Start CLI bot daemon"
echo "    cgctl monitor            Attach live TUI"
echo ""
echo "  ── STEP 2: TELEGRAM BOT SETUP ──"
echo "    1. Open Telegram → search @BotFather"
echo "    2. Send /newbot → choose name → get token"
echo "    3. cgctl tg env           Paste your token"
echo "    4. cgctl tg start         Start Telegram bot"
echo "    5. Open your bot in Telegram → /start"
echo ""
echo "  ── DAILY USE ──"
echo "    cgctl start-all           Start both bots"
echo "    cgctl stop-all            Stop both bots"
echo "    cgctl status-all          Check all services"
echo ""
echo "    cgctl tg status           Telegram bot status"
echo "    cgctl tg logs             Telegram bot logs"
echo "    cgctl tg restart          Restart after config change"
echo ""
echo "  ── FILES ──"
echo "    Bot:        $INSTALL_DIR/"
echo "    CLI Config: ~/.cryptogames_autobot.json"
echo "    CLI DB:     ~/.cryptogames_autobot.db"
echo "    TG Data:    ~/.cryptogames_tg/<user_id>/"
echo "    Env:        $INSTALL_DIR/.env"
echo "    Logs:       cgctl logs / cgctl tg logs"
echo ""
