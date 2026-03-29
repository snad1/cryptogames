# Changelog

## v1.0.3 — Security Hardening (2026-03-29)

### TG Bot v1.0.3

#### Security

- **ENV-controlled error messages** — Error handlers now log full details server-side and show user-friendly messages in production. Controlled via `APP_ENV` environment variable
- **`cgctl` self-update safety** — Script wrapped in `{ }` block to prevent parse errors when `cmd_update` replaces the file mid-run

---

## v1.0.2 — Stats, Status, Rule Editor & Web Fixes (2026-03-26)

### CLI Bot v1.0.2

#### Added

- **Enhanced `cmd_stats()`** — Full per-session details: speed (BPS/BPM peak/low), balance extremes, average P/L, uptime; plus an all-time totals section across all sessions
- **Enhanced `cmd_status()`** — Full 30-metric display including stop conditions, active rules, speed ranges, and win/loss streaks
- **`_compute_streak_distribution()`** — Per-session bet analysis for win/loss streak frequency; used in stats and session detail views
- **`_edit_one_rule()` interactive rule editor** — Edit existing rules in-place via the setup wizard; wired into the main configuration flow

### TG Bot v1.0.2

#### TG Bot Added

- **`tg/strategy.py` re-export module** — Thin re-export so Telegram bot imports strategy helpers from the shared core without path hacks

### Web Admin v1.0.2

#### Web Admin Added

- **`web/static/app.css`** — Main stylesheet for the web admin UI (was missing, causing unstyled pages)
- **`web/static/app.js`** — Main frontend JS for the web admin UI (was missing, causing non-functional pages)
- **`web/static/chart.js`** — Chart helper used by the balance chart view (was missing)
- **`web/.env.testing`** — Test environment config for running web tests against the testing database

---

## v1.0.1 — Data Retention & Cleanup (2026-03-24)

### TG Bot v1.0.1

#### Added

- **Automatic bet cleanup** — Old bet records (3+ days) from ended sessions are automatically purged when a new session starts. Session statistics (profit, bets, streaks, balance extremes, speed) are preserved — only raw bet rows are deleted. Disk space is reclaimed via VACUUM.
- **`/cleanup [days]`** — Manually purge bet records older than N days (default 3). Session stats remain intact. Usage: `/cleanup` or `/cleanup 1`.
- **`/delsession <id>`** — Delete a specific session and all its bets by session ID. Blocks deletion of currently running sessions. Shows bet count and profit before confirming.
- **`bets_purged` flag** — Sessions table gains a `bets_purged` column to track which sessions have already been cleaned, avoiding redundant queries on subsequent cleanups.

## v1.0.0 — Initial Release (2026-03-21)

### Full Stack

- **CLI bot** (`cryptogames.py`) — Interactive wizard, Pure ANSI TUI dashboard, daemon mode, monitor mode, presets.
- **Telegram bot** (`tg/`) — 27 commands, per-user isolation, multi-session (up to 5 concurrent), inline keyboards, auto-command registration.
- **Web dashboard** (`web/`) — FastAPI admin panel with JWT auth, per-user session views, CSV export, WebSocket live updates, audit log.
- **Shared core** (`core/`) — Single source of truth for strategies, database schema, and bet computation.
- **Server installer** (`install.sh`) — Systemd services, venv, `cgctl` management CLI.

### Features

- **8 strategies** — Flat, Martingale, Anti-Martingale, D'Alembert, Paroli, CryptoRider, Delay Martingale, Rule-Based.
- **21 rule actions** — Bet amount, win chance, payout multiplier, switch, stop, reset.
- **15 currencies** — BTC, ETH, USDT, XRP, BNB, SOL, USDC, DOGE, SHIB, LTC, BCH, PEPE, ETC, POL, PLAY.
- **Dice game** — Over/Under prediction with customizable payout multipliers.
- **Smart stop conditions** — Max profit, max loss, max bets, max wins, min balance.
- **Named presets** — Save & load strategy configs by name.
- **Performance tracking** — BPS, BPM, peak/low speed, peak/low balance, best win, worst loss.
- **Multi-session support** — Up to 5 concurrent sessions per Telegram user.
- **Zero-downtime updates** — `cgctl update` with session auto-resume.
- **Benchmark command** — `/benchmark` to test API response speed.
- **Base bet validation** — Validated against `MinBet` from API before session starts.
- **Fatal error handling** — Session stops cleanly on API errors with friendly notifications.

### Post-Release Fixes

- Fix TG balance fetch: use `/v1/BalanceAll` endpoint, send numeric bet fields.
- Fix TG currencies list to match actual crypto.games supported coins.
- Validate currency against supported coins list in `/set` command.
- Update currencies to match current crypto.games supported coins.
- Validate base bet against coin `MinBet` from API before starting session.
- Stop session on fatal API errors and show friendly stop notifications.
- Add web dashboard installer and requirements.
- Add change password page for admin users.
- Fix change password: look up admin by DB id, not username.
- Add `/benchmark` command and API timing to status display.
- Fix accessibility: add label associations and placeholders to change password form.
