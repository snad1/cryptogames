# Changelog

## TG v1.9.0 — Streak reset, delay caps, analytics window (2026-11-14)

Mirrors WolfBet TG 1.20.0: v2.30.6 (delay cap), v2.32.0 (streak reset), v2.32.1 (insufficient balance terminal), v2.33.0 (time-of-day window). CLI unchanged. Dice only; the `ClientSeed` rotation after each bet is unchanged.

- **Streak reset** — `/set srloss N` (alias `streakreset`, `off` to disable) stops the session on the first win after N+ consecutive losses, only while profit ≥ 0. The bot then starts a new session (new `sessions` row) after `/set srdelay S` (alias `streakresetdelay`, default 600 s, 5–86400), **even when `recurring` is off**. Live `/set srloss|srdelay` carries into the next cycle; the bumped `base_bet` is kept and `next_profit_milestone` re-arms from `profit_threshold`. Uses `shared.core.session_rules` (`record_outcome`, `streak_reset_triggered`, `STREAK_RESET_REASON`).
- **Delay caps** — `/set recdelay` and `/set srdelay` clamp to 5..86400 and tell you when they clamp. A saved `recurring_delay` above 24 h is capped at the restart.
- **`/tweak`** gains `srloss` (live on the running engine) and `srdelay` / `recdelay` (saved; apply at the next stop).
- **`/config`, `/status`, stop message** show `Streak reset … / SR nL→Ss` when set; `/help` lists the keys; web settings page lists `streak_reset_losses` / `streak_reset_delay`; both keys are in `CONFIG_KEYS` (presets) and the `/resume` snapshot.
- **`/analytics`** builds its window with `shared.core.stats.stats_date_window`: `/analytics 2026-11-13 14:00` now starts at 14:00 instead of matching the whole day (`' ' < 'T'`). A time token after a date joins it, since Telegram splits on spaces. Bad bounds print the usage.
- **Fix: insufficient-balance match.** The HTTP-200 error-body path and the generic exception path of `_api_place_bet` stopped the session on any message containing "balance" (`"insufficient" or "balance"`), the same bug as goated and shuffle. They now match "insufficient" only. Insufficient balance stays terminal: no recurring or streak-reset restart. (The CLI has the same match; fixed in its E3 story.)
- N/A for TG: none of the v2.32.0–v2.33.0 TG items depend on WolfBet-only API features.
- Tests: `tests/test_wolfbet_sync_e2.py` (27); fake gains `api_error_balance`. `test_portability_v1.py` version pin and the `/analytics` source check updated for the shared helper.

`tg/__init__.py` `1.8.1` → `1.9.0`.

## CLI v1.6.1 / TG v1.8.1 — casino-shared over HTTPS (2026-11-13)

Mirrors wolfbet v2.16.11 (casino-shared dependency installs over HTTPS). No bot behaviour change.

- **`requirements.txt`, `web/requirements.txt`: `casino-shared` via `git+https://github.com/snad1/casino-shared.git` instead of `git+ssh://`.** The repo is public, so pip fetches it anonymously; fresh servers no longer need a GitHub SSH key to run `install.sh`.
- **`cgctl update`** reinstalls casino-shared from the same HTTPS URL (it used `git+ssh` too).
- **Pinned to casino-shared `v0.2.0`** (`@v0.2.0`): the WolfBet sync helpers (`shared.core` session rules, stats, diagnostics, net, lanes and `sessions.lane`). `cgctl update` still reinstalls the latest `main`, as `wolfctl` does.

`VERSION` `1.6.0` → `1.6.1`. `tg/__init__.py` `1.8.0` → `1.8.1`.

## CLI v1.6.0 / TG v1.8.0 — Date-range stats + analytics (2026-08-15)

Mirrors wolfbet v2.30.9/v2.31.0: date-window evaluation of existing history, everywhere stats are shown.

### CLI — `--stats --since DATE [--until DATE]`

- **`--since` / `--until`** (standalone parser args, work alongside the `--stats` group member): bare dates (`YYYY-MM-DD`) or full ISO timestamps; a bare `--until` is extended to end-of-day (`T23:59:59`) so the day is inclusive. ISO strings compare correctly lexically in SQLite.
- New `_stats_date_window(since, until)` helper builds the parameterized `WHERE started_at >= ? AND started_at <= ?` clause shared by the session-list and totals queries.
- `cmd_stats(since, until)` threads the window into both queries; the listing limit rises to **50** when a window is active (20 default). Headers show the window and the totals block reads `Range Totals` vs `All-Time Totals`.
- `cgctl stats` now passes args through (`cgctl stats --since 2026-08-14` works).

### TG — `/analytics [SINCE] [UNTIL]`

- `/analytics 2026-08-14` → windowed lifetime + by-game + by-strategy + top-5 blocks; header shows the window (`Range analytics` vs `Lifetime analytics`).
- `/analytics 2026-08-01 2026-08-15` → explicit window; bare UNTIL date = inclusive end of day.
- `>2 args` → friendly usage hint (never a traceback).
- `/help` documents the date form.
- Same window semantics as the CLI (parameterized, all five queries share the `{where}` clause).

**Tests**: `tests/test_portability_v1.py` grows to 29 — `_stats_date_window` unit checks (empty / since-only / bare-until end-of-day), functional `cmd_stats(since=…)` against a seeded temp DB (window filters sessions, `Range Totals` header; no-filter `All-Time` regression), argparse source shape (`--since` standalone, dispatch threading), TG source shape (`context.args` parsed, `{where}` in all 5 queries, Range header), `/help` mention, version assertions.

`VERSION` `1.5.0` → `1.6.0`. `tg/__init__.py` `1.7.0` → `1.8.0`. `cgctl` gained `"$@"` passthrough on `stats`.

## CLI v1.5.0 / TG v1.7.0 — WolfBet hardening subset ported (2026-07-19)

Ports the portable subset of the wolfbet v2.27-v2.30 hardening wave. No behaviour change to the bet loop.

- **SQLite PRAGMAs** — `synchronous=NORMAL`, `busy_timeout=5000`, `cache_size=-32000`, `temp_store=MEMORY` on top of the existing `journal_mode=WAL`, on both CLI (`_db_conn`) and TG (`BettingEngine._get_conn`) connection paths. Kills 30–40 ms per-commit fsync on typical VPS SSD. WAL-safe.
- **systemd `Restart=on-failure`** — replaces `Restart=always` in `install.sh` for both the daemon and TG units. Prevents "stopped by user" being reversed by systemd.
- **Uptime pause bookkeeping** — new `session_bet_ended_at` + `session_pause_started_at` fields on `BettingEngine`. `pause()` freezes both, `resume()` clears. `get_status()` uses the frozen bet-end as the uptime ceiling. `_db_save_session(final=True)` writes the frozen `ended_at` so DB session runtime no longer includes pause time. New `uptime_sec` + `pause_remaining_sec` keys on the status dict.
- **Row 6 monitor config-progress row** — the old `" P/L —"` sparkline placeholder is replaced by a compact `CFG` summary showing profit-milestone %, active stop conditions (`MaxP`/`MaxL`/`MaxB`/`MaxW`) with `current/target (pct%)` progress, `MinBal` proximity, and `Rec on(Xs)` when recurring. Green <80%, yellow ≥80%, bold-red ≥95% visual alarm. Fallback `" CFG  ─  no goals set"` when nothing is armed.
- **TG `/diagnose`** — new bottleneck analysis command (top blocker among Network / CLI overhead / User delay + advice).
- **TG `/analytics`** — new lifetime aggregates command (per-game + per-strategy + top-5 best/worst).
- **First test suite** — `tests/test_portability_v1.py` (21 tests) locks all of the above.

`VERSION` `1.4.0` → `1.5.0`. `tg/__init__.py` `1.6.10` → `1.7.0`. `cgctl` unchanged.

## v1.6.10 — `/status` speed block trimmed (2026-06-17)

### Changed

- **Removed `Overhead` line** from the `/status` speed block — rarely actionable at a glance, adds noise.
- **`API stable` and `Efficiency` now render only when `bet_delay > 0`.** With no delay set, the theoretical-max reference is meaningless and median-vs-target has no target — both lines were pure clutter. When the user does set a delay, both lines render as before.

## v1.6.9 — Session-ended notification: green ✅ on profit, red 🛑 on loss (2026-06-17)

### Changed

- **`Session #X ended` notification now leads with `✅`** when the session ended with `profit >= 0`, keeping `🛑` for `profit < 0`. Previously every stop-notification opened with `🛑` regardless of outcome — a `max_profit` hit still triggered a red-icon push. Leading emoji is now driven by the sign of `s["profit"]`; every other line is unchanged.

## v1.6.8 — Fix: `/status` rendering as plain text — `bet_delay` opened an unclosed italic entity (2026-06-17)

### Fixed

- **`/status` rendered as PLAIN TEXT** (literal `*Session #X*`, `*Balance*`, `` `…` `` visible) because the v1.6.7 fallback was firing every invocation. Root cause: the literal token `bet_delay` on the "API stable" line sat OUTSIDE any code span — Markdown V1 read the `_` as the start of an italic entity, never found the closing `_`, and rejected the message. Renamed to `bet delay` (space, not underscore) — same meaning, no Markdown bomb. The v1.6.7 fallback remains in place as the safety net.

## v1.6.7 — Fix: `/status` silently failing on Markdown parse error (2026-06-17)

### Fixed

- **`/status` returns nothing in Telegram** when a rule description or engine status string contains an unbalanced Markdown character. `format_status` wraps user/external strings inside Markdown V1 code spans (`` `…` ``); a stray backtick splits the entity and Telegram silently rejects the message. Fixed at the render boundary — `_safe_code(s)` escapes backticks in the two leaky fields (rule descriptions, trailing engine status). Added `safe_reply_markdown(...)` wrapper for `/status` and `/monitor`; enhanced `_safe_send` and the monitor-refresh `edit_text` paths to retry as plain text on parse-error `BadRequest`. The user always sees the message; technical detail is logged server-side only.

## v1.6.6 — Fix: SQLite cross-thread error in _get_conn (defensive) (2026-06-17)

### Fixed

- **`DB flush_bets failed: SQLite objects created in a thread can only be used in that same thread.`** — `_get_conn` now opens directly with `sqlite3.connect(..., check_same_thread=False)` instead of via shared `db_connect`, so a stale pip-installed casino-shared can't reintroduce the bug.

## v1.6.5 — API stable: median + on-target % (2026-06-17)

### Added

- **`API stable: Xms median / Y% on-target`** — median = typical API time (unbiased by spikes); on-target % = bets where API ≤ bet_delay. Explains the Efficiency ceiling.

## v1.6.4 — Efficiency % indicator (2026-06-17)

### Added

- **`Efficiency: X%`** on the dashboard — bot's actual recent bps as a % of the theoretical max (= 1 / max(bet_delay, api_avg)). Single number that answers "is the bot at peak?".

## v1.6.3 — API peak time on the dashboard (2026-06-17)

### Added

- **`API: X last / Y avg / Z peak`** — third field tracks the slowest single API response observed this session.

## v1.6.2 — Cycle metric: full per-bet time (bps reciprocal) (2026-06-17)

### Added

- **`Cycle: Xms/bet`** on the dashboard — exp-smoothed time between consecutive bet starts. This is the bps reciprocal (`Cycle × bps ≈ 1000`), shown inline as `(1000/385 = 2.60 bps)`. Complements `Overhead` (post-API processing only) — `Cycle` is the honest end-to-end number.

## v1.6.1 — Per-cycle overhead diagnostic + get_status() cache (2026-06-17)

### Added

- **`Overhead: Xms/bet`** on the dashboard — exp-smoothed time per bet OUTSIDE of `bet_delay` and the API call. Healthy = ~5–15ms; 50ms+ = investigate.
- **`get_status()` cache (250ms TTL)** — eliminates the brief per-second bucket dip at milestones.

## v1.6.0 — Sliding-window BPS + non-blocking SQLite writes (2026-06-17)

### Added

- **`Now` bps (sliding 60s window)** alongside the existing cumulative `Avg` — dashboard now shows both.

### Changed

- **DB writes no longer block the event loop.** `_flush_bets`, `_db_save_session`, and `cleanup_live_bets` now run via `asyncio.to_thread`. Inline batch-size flush trigger removed. Shared `db_connect` now opens with `check_same_thread=False`.

Result: multiple concurrent sessions scale closer to single-session throughput.

## v1.5.0 — Auto-revive: systemd retry-forever + external stall watchdog (2026-06-17)

### Added

- **`Restart=always` + `StartLimitIntervalSec=0`** on both CLI and TG bot services.
- **External stall watchdog timer** — `cryptogames-tg-watchdog.timer` fires every 2 min; if `/tmp/cryptogames-tg.heartbeat` is older than 180s, restarts `cryptogames-tg`.
- **Heartbeat task** — `_heartbeat_loop()` writes the heartbeat file every 30s from `post_init`.

If the bot crashes, systemd brings it back in 10s. If it stalls, the watchdog brings it back within ~3 min. No more SSH-and-restart.

## v1.4.8 — /update cd's into repo dir before running ctl (2026-06-11)

### Fixed

- **/update failed with "No cryptogames.py in current directory"** — `systemd-run` spawns bash with cwd=/. Now `cd /root/cryptogames && cgctl update` is the bash command. Override via `BOT_REPO_DIR` env var if your layout is different.

## v1.4.7 — /update reports real errors + writes update log (2026-06-10)

### Fixed

- **/update silently failed when systemd-run errored** — Previous `subprocess.Popen` with `stderr=DEVNULL` swallowed failures. Now uses `subprocess.run --no-block` synchronously, captures stdout/stderr, surfaces real errors to Telegram. Update output goes to `/tmp/cgctl-update.log` so you can review what happened: `cat /tmp/cgctl-update.log`.

## v1.4.6 — /update Telegram command for self-update (2026-06-10)

### Added

- **`/update` Telegram command (owner-only)** — Pull latest code from git, copy files, reinstall `casino-shared`, restart the bot. Equivalent to running `cgctl update` over SSH, but triggered from Telegram. Owner gate via `TG_OWNER_ID` env var (defaults to your user ID if unset). Implementation spawns `cgctl update` via `systemd-run --user --collect` so the update survives the bot getting killed by the restart.

## v1.4.5 — Remove 5-session concurrency limit (2026-05-12)

### Changed

- **Unlimited concurrent sessions per user** — `MAX_SESSIONS = 5` cap removed from `/bet` and from the recurring-restart path. Users can now run as many concurrent sessions as they want (limited only by the casino's own API rate limits, which are shared across sessions).

## v1.4.4 — bet_delay is a minimum-interval, not a sleep-before (2026-05-11)

### Changed

- **`bet_delay` semantics** — Previously: `sleep(bet_delay)` before each bet, so cycle = `bet_delay + api_time`. Now: minimum interval since the previous bet *started*, so cycle = `max(bet_delay, api_time)`. With delay=1s and api=50ms, you get a clean 1 bet/sec; with api=1500ms there's no extra sleep so the bot keeps up. More predictable pace.

## v1.4.3 — Visible 429 logging + status updates (2026-05-11)

### Fixed

- **429s were happening silently** — `_set_error` only logged when a `technical` argument was passed, but the 429 handler called it with only the friendly message. Result: bot retried 429s invisibly while the dashboard kept showing "Placing bet #N..." with no logs explaining what was happening.
  - Every 429 now logs immediately: `HTTP 429 on bet #N (Retry-After=X, body=…)`.
  - During the 429 backoff wait, `self.status` updates to e.g. `Rate limited (429 #3) — waiting 4s (total 7s)` so the dashboard reflects what the bot is doing.
  - Each backoff sleep logs `429 #N — waiting Xs (cumulative Ys/1800s)` for full visibility.
  - Connection timeouts also now log explicitly with the exception type and streak count.

## v1.4.2 — Rate-limit storms no longer kill sessions (2026-05-11)

### Fixed

- **Session killed by sustained 429 storm** — Long-running session (40h, 139k bets, +18 USDT) ended with "Too many consecutive errors: Rate limit reached — cooling down" because 429 responses were counted toward the same `consecutive_errors` bucket as real failures. With max backoff 30s and a 10-error threshold, the session died after ~3 minutes of rate-limiting — too tight for CryptoGames' actual rate-limit windows.
  - 429 responses tracked in a separate `_consecutive_429` counter; session only gives up after **cumulative rate-limit wait exceeds 30 minutes**.
  - **Probing backoff schedule** (since CryptoGames doesn't return rate-limit headers): 1s, 2s, 4s, 8s, 16s, 30s, 30s, 30s, … (cap at 30s). The short early intervals discover when the window clears even if it's only a few seconds; the 30s cap keeps wait bounded if the window is longer.
  - Honors `Retry-After` header if present (overrides the schedule).
  - Real errors (timeouts, bad responses) still kill the session at 10 consecutive — unchanged.

## v1.4.1 — Fix _safe_send infinite recursion (2026-05-02)

### Fixed

- **`_safe_send` infinite recursion** — The function was calling itself instead of `app.bot.send_message`, causing `RecursionError: maximum recursion depth exceeded` on every Telegram notification (stops, milestones, errors). Fixed to call `app.bot.send_message` directly.

## v1.4.0 — Recurring honors live config across all running sessions (2026-04-28)

### Fixed

- **Recurring only applied to sessions started AFTER `/set recurring on`** — Previously, `recurring_state` was registered at `/bet` time only if `config.get("recurring")` was true at that moment. If a user started a session, then later toggled recurring on and started another session, only the second one would auto-restart on stop — the first had no recurring entry. Now `recurring_state` is registered for every session unconditionally (per-slot snapshot of game/strategy preserved). At stop time the engine re-reads the user's saved config to decide whether to actually fire the restart, so toggling `/set recurring on/off` applies instantly to **every** running session regardless of game type.
- **Recurring lost across bot restart** — `load_resume_state` now also registers `recurring_state` for each resumed session so a stop after a bot update still triggers the configured restart.
- **Notification throttle now driven by live config** — The "is this a recurring session" check used for stop-message rate-limiting now reads the live `recurring` flag instead of the snapshot, matching the new behavior.

Per-session game/strategy isolation is preserved: each session's snapshot keeps its own game/strategy/rule etc., so a session restart stays the same game even with multiple games running concurrently.

## v1.3.0 — Streak Delay Bets (2026-04-21)

### Added

- **`streakdelay_bets`** — Delay every N total bets by X seconds, regardless of win/loss outcome. Format `N:seconds` (e.g. `/set streakdelay_bets 100:0.5` pauses 0.5s every 100 bets). Useful for throttling overall bet rate independent of streaks. Live-tweakable via `/tweak sdbets 100:0.5`. When multiple streak delays apply on the same bet (e.g. loss streak + bet count), the longest delay wins

## v1.2.2 — Recurring Notification Throttle (2026-04-21)

- **Telegram flood ban on fast recurring sessions** — Stop and start notifications are now rate-limited to at most one of each per 30 seconds per user during recurring cycles. Losses, errors, insufficient balance, and manual stops are always sent immediately regardless of throttle

## v1.2.1 — Recurring Restart Reliability & Task Safety (2026-04-21)

### Fixed

- **Fire-and-forget task exceptions now logged** — Added `_log_task_exception` done-callback to all `create_task` calls so unhandled exceptions are surfaced in logs instead of being silently swallowed
- **`_notify_stop` formatting errors caught** — Wrapped `format_stop` call in try/except; falls back to plain stop message so the bot never crashes on a bad status snapshot
- **`ensure_future` replaced with `create_task`** — All callback factories (`_make_on_stop`, `_make_on_milestone`, `_make_on_error`) now use `asyncio.create_task` with done-callbacks for proper error visibility
- **Recurring restart retries on engine-start failure** — When `engine.start()` returns false, the session is re-queued after the configured delay instead of being silently dropped
- **Monitor loop stays alive during restart gap** — `_monitor_loop` now continues iterating while a recurring restart timer is pending, showing "Recurring restart pending…" instead of prematurely exiting
- **Inline keyboard preserved during restart gap** — `refresh_status` callback keeps Refresh/Stop buttons visible with a pending message while waiting for the next recurring restart

## v1.2.0 — Adaptive Base Bet & Full Config Visibility (2026-04-14)

### Added

- **`basebet_pct`** — Set base bet as a fraction of current balance (e.g. `/set basebet_pct 0.001` = 0.1%). Recomputes on session start and at every profit-increment milestone, so base bet auto-shrinks during drawdowns and grows during profit. Live-tweakable via `/tweak bbpct 0.001`
- **`streakbet_loss`** — Reduce (or scale) bet after N consecutive losses. Format `N:multiplier` (e.g. `/set streakbet_loss 10:0.5` halves bet every 10 losses). Damping floor for Martingale-style strategies. Live-tweakable via `/tweak sbloss 10:0.5`

### Changed

- **Full config in every surface** — Session-start message, `/status`, and stop summary now display every active setting: streak delays, streak bet, basebet pct, profit bump + next milestone, milestone cadence, stops, rule, win/loss multipliers. Single `format_full_config` helper in formatter; no more drift between surfaces

## v1.1.4 — Insufficient Balance Stop (2026-04-13)

### Fixed

- **Insufficient balance now always stops session** — Added pre-bet balance guard (`current_bet > current_balance`) and broadened non-200 HTTP response detection. Previously, deep Martingale streaks could drive `current_bet` above balance without the session stopping

## v1.1.3 — Streak Delay & Recurring Bet Fixes (2026-04-09)

### Added

- **Streak delay** — Delay next bet after N consecutive wins/losses. Configure with `/set streakdelay_loss 5:1.0` (every 5 losses → 1s delay) and `/set streakdelay_win 10:0.5`. Works with all strategies including auto-bet. Live tweak with `/tweak sdloss 5:1.0` / `/tweak sdwin off`
- **Streak delay in /config** — Displays streak delay settings in configuration output

### Fixed

- **Recurring bet preserves profit increment** — When a session stops and recurring restarts, the current (profit-incremented) base_bet is now carried forward instead of resetting to the original config value. Useful for short recurring sessions to bypass server-side throttling while maintaining bet progression

## v1.1.2 — Bug Fixes (2026-04-07)

### Fixed

- **Live bet cleanup** — ISO timestamp `T` separator caused comparison failure with SQLite's `datetime()`. Bets older than purge_days now correctly deleted during running sessions
- **Telegram timeout on session start** — Session start confirmation wrapped in try/except. Session continues even if Telegram times out
- **Milestone bets=0** — Setting `milestonebets` to 0 now properly disables (was defaulting to 100)
- **Help text** — Added missing cleanup, delsession, purgedays commands

---

## v1.1.1 — Safety, Cleanup, Charts (2026-04-03)

### Added

- **Live bet cleanup** — Bets older than N days auto-deleted every hour during running sessions. `/set purgedays 1` (default 1, range 1-30)
- **Chart snapshots** — Profit/balance saved every 100 bets. Web charts survive bet cleanup
- **Profit increment = 0** — Creates new sessions at profit threshold without increasing base bet

### Fixed

- **CK audit** — 65 scientific notation violations fixed across all services
- **`/tweak basebet` safety** — No longer kills strategy recovery during loss streak (applies on next win)

---

## v1.1.0 — Async Engine, /tweak, Proxy (2026-04-02)

### Added

- **Async engine** — TG betting engine converted from blocking threads to async I/O. Multiple sessions run truly concurrent instead of competing for Python's GIL
- **`/tweak` command** — Live-edit running sessions without stopping: delay, stop conditions (maxwins, maxbets, maxprofit, maxloss, minbalance), milestones, basebet, multiplier, loss/win mult
- **Per-session proxy** — Route each session through a different IP: `/set proxy http://user:pass@ip:port` or `socks5://...`
- **Production-safe errors** — `_set_error()` method ensures raw API errors never leak to users in production

### Changed

- HTTP client: `requests.Session` → `httpx.AsyncClient`
- Threading: `threading.Thread` → `asyncio.create_task`
- Sleep: `time.sleep` → `asyncio.sleep`
- Callbacks: `run_coroutine_threadsafe` → `asyncio.ensure_future`
- Suppressed httpx/httpcore polling log noise

---

## v1.0.8 — Recurring Bets & Zero-Balance Start (2026-03-29)

### Added

- **Recurring bet feature** — Sessions auto-restart after configurable delay when stopped by conditions (profit target, max bets, etc). Configure with `/set recurring on|off` and `/set recurringdelay <seconds>`. Cancel with `/stop recurring`

### Fixed

- **Zero-balance TG start** — TG engine now allows zero-balance sessions when base bet is 0 (previously blocked with "No balance found")

---

## v1.0.7 — Fix BPM Calculation (2026-03-29)

### Fixed

- **BPM calculation** — `bets_per_minute` was set to raw count of bets in the current calendar minute instead of the actual rate; now correctly derived as `bets_per_second * 60`

---

## v1.0.6 — Insufficient Balance Fix (2026-03-29)

### Fixed

- **Insufficient balance detection** — CLI and TG now properly detect "insufficient balance" in API error responses and stop the session immediately
- **TG error notification** — Added `on_error` callback; sends `⚠️ Insufficient balance` message to user via Telegram before stopping

---

## v1.0.5 — Shared Library as pip Package (2026-03-29)

### Infrastructure

- **casino-shared pip package** — `shared/` library now installable via `pip install casino-shared` from GitHub, eliminating manual file copying on servers
- **requirements.txt** — Added `casino-shared @ git+ssh://git@github.com/snad1/casino-shared.git` to both bot and web requirements
- **install.sh** — Added `shared/` copy step as fallback for offline/non-pip installs
- **cgctl update** — Now syncs `shared/` library alongside core/tg during updates

---

## v1.0.4 — DRY Shared Library Extraction (2026-03-29)

### Infrastructure

- **Shared library extraction** — Extracted ~6,600 lines of duplicated code into `shared/` library used across all 6 casino bots
  - `web/websocket.py`, `web/database.py`, `web/auth.py`, `web/services.py`, `web/bot_db.py`, `web/routes/auth_routes.py` — thin shims delegating to shared modules
  - `tg/database.py` — thin shim binding `DATA_DIR` to shared persistence
  - `core/strategy.py` — keeps local STRATEGIES dict, delegates rule engine to shared
  - `core/database.py` — keeps local `init_db`, delegates utilities to shared
- Zero downstream import changes — all existing imports continue working

### Security

- **Shell injection fix** — Replaced `create_subprocess_shell` with `shutil.copy2` in update flow
- **Deprecated datetime fix** — Replaced `datetime.utcnow()` with `datetime.now(timezone.utc)`
- **Narrowed exception handling** — Replaced broad `except Exception` with specific types
- **Removed unused imports** — Cleaned up unused `import os` from shims

### Testing

- **114-test suite** added covering all shared modules

---

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
