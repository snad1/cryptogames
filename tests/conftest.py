"""Test sandbox + fake casino fixtures (E0-S2).

Module top runs before any test imports `cryptogames` or `tg`: path constants
are bound at import from CRYPTOGAMES_* / CRYPTOGAMES_TG_DATA / HOME, so they
must point at a temp dir first. Each test then gets its own tmp paths, a fresh
CLI `state`, and non-waiting sleeps.
"""

import asyncio
import os
import sys
import tempfile
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_CASINO = os.path.dirname(_ROOT)
for _p in (_ROOT, _CASINO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SANDBOX_HOME = tempfile.mkdtemp(prefix="cryptogames_home_")
os.environ["HOME"] = _SANDBOX_HOME
os.environ["APP_ENV"] = "testing"
os.environ.pop("CRYPTOGAMES_API_BASE", None)
os.environ["CRYPTOGAMES_TG_DATA"] = os.path.join(_SANDBOX_HOME, "tg")
os.environ["CRYPTOGAMES_LOG_DIR"] = os.path.join(_SANDBOX_HOME, "logs")
for _name in ("DB_PATH", "CONFIG_PATH", "STATE_PATH", "PID_PATH", "PRESET_PATH"):
    os.environ[f"CRYPTOGAMES_{_name}"] = os.path.join(_SANDBOX_HOME, _name.lower())

import cryptogames as cg  # noqa: E402
from tg import engine as tg_engine, database as tg_database  # noqa: E402

from .fakes import FakeCasino  # noqa: E402

_real_async_sleep = asyncio.sleep


@pytest.fixture
def sleeps():
    """Durations the code asked to sleep (CLI time.sleep + TG asyncio.sleep)."""
    return []


@pytest.fixture(autouse=True)
def _sandbox(tmp_path, monkeypatch, sleeps):
    for name in ("DB_PATH", "CONFIG_PATH", "STATE_PATH", "PID_PATH", "PRESET_PATH"):
        monkeypatch.setattr(cg, name, str(tmp_path / f"cli_{name.lower()}"))
    monkeypatch.setattr(tg_database, "DATA_DIR", str(tmp_path / "tg"))
    monkeypatch.setattr(cg, "state", cg.BotState())

    def _no_live(*a, **k):
        raise AssertionError("live HTTP request from a test (patch cg._http_session)")
    monkeypatch.setattr(cg._http_session, "request", _no_live)
    monkeypatch.setattr(cg._http_session, "proxies", {})

    async def fast_sleep(delay, *a, **k):
        sleeps.append(delay)
        await _real_async_sleep(0)

    monkeypatch.setattr(cg.time, "sleep", sleeps.append)
    monkeypatch.setattr(tg_engine.asyncio, "sleep", fast_sleep)
    yield


@pytest.fixture
def fake_casino():
    return FakeCasino(balance=10.0, coin="doge", api_key="test-key")


@pytest.fixture
def cli_state(fake_casino, monkeypatch):
    """Factory: configured CLI BotState with a started session on the fake."""
    def make(max_bets=10, **overrides):
        api = fake_casino.requests_api()
        monkeypatch.setattr(cg.requests, "get", api.get)
        monkeypatch.setattr(cg.requests, "post", api.post)
        # v1.9.0 — the CLI calls the API through `_http_session` (proxy support).
        monkeypatch.setattr(cg._http_session, "get", api.get)
        monkeypatch.setattr(cg._http_session, "post", api.post)
        cg.init_db()
        s = cg.state
        s.api_key = fake_casino.api_key
        s.currency = fake_casino.coin
        s.game = "dice"
        s.rule = "under"
        s.multiplier = 2.0
        s.strategy = "Flat Bet"
        s.strategy_key = "1"
        s.base_bet = s.current_bet = 0.01
        s.max_bets = max_bets
        bal = fake_casino.balance
        s.start_balance = s.current_balance = s.highest_balance = s.lowest_balance = bal
        for k, v in overrides.items():
            setattr(s, k, v)
        s.session_id = cg._db_start_session()
        s.session_start = time.time()
        s.running = True
        return s
    return make


@pytest.fixture
def run_cli():
    """Run the real CLI betting loop on the main thread until it stops."""
    def run():
        cg.betting_loop()
        return cg.state
    return run


@pytest.fixture
def tg_engine_factory(fake_casino, tmp_path, monkeypatch):
    """Factory: real TG BettingEngine whose HTTP client is the fake casino."""
    async def fake_recreate(self):
        if self._http:
            await self._http.aclose()
        self._http = fake_casino.async_client()

    monkeypatch.setattr(tg_engine.BettingEngine, "_recreate_http", fake_recreate)

    def make(max_bets=10, **cfg):
        config = {
            "currency": fake_casino.coin, "rule": "under", "multiplier": 2.0,
            "base_bet": 0.01, "strategy": "Flat Bet", "strategy_key": "1",
            "max_bets": max_bets,
        }
        config.update(cfg)
        e = tg_engine.BettingEngine(user_id=1, db_path=str(tmp_path / "tg.db"),
                                    api_key=fake_casino.api_key, config=config)
        e.stops, e.errors = [], []
        e.on_stop = e.stops.append
        e.on_error = e.errors.append
        return e
    return make


@pytest.fixture
def run_tg():
    """Start the engine and wait for its betting task to finish."""
    def run(engine):
        async def _run():
            assert await engine.start(), engine.last_error
            await engine._task
        asyncio.run(_run())
        return engine
    return run
