"""Cryptogames CLI parallel lanes (CLI v1.10.0).

Mirrors WolfBet v2.35.0 (parallel lanes) and v2.36.0 (`lane_split`). Lane
helpers come from shared.core.lanes. Reference test:
wolfbet/tests/test_phase10_lanes.py. N/A on cryptogames: soft pacing and the
/auto/start lock (no server auto-bet, no rate-limit quota headers).

L7 seed rule: crypto.games takes `ClientSeed` in every placebet body and the
server seed is server-managed, so each lane rotates its own ClientSeed.

Run: APP_ENV=testing .venv-test/bin/python -m pytest cryptogames/tests -q
"""

import importlib.util
import json
import logging
import os
import signal
import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest

import cryptogames as cg
from shared.core.session_rules import should_restart

from .fakes import FakeCasino, RequestsAPI

FORBIDDEN = ("api_key", "currency", "proxy", "purge_days", "db_write_mode")


@pytest.fixture(autouse=True)
def _lane_sandbox(monkeypatch):
    """Lane paths derive from the sandboxed base paths; log format restored."""
    monkeypatch.setattr(cg, "_BASE_STATE_PATH", cg.STATE_PATH)
    monkeypatch.setattr(cg, "_BASE_PID_PATH", cg.PID_PATH)
    fmt = cg._log_handler.formatter
    yield
    cg._log_handler.setFormatter(fmt)


@pytest.fixture
def saved_config(cli_state):
    cli_state(base_bet=0.01)
    cg.state.running = False
    cg.save_config()
    return Path(cg.CONFIG_PATH)


def _raw(path) -> dict:
    return json.loads(Path(path).read_text())


def _write_lanes(path, **lanes):
    data = _raw(path)
    data["lanes"] = lanes
    Path(path).write_text(json.dumps(data))


def _fresh_load(lane=1):
    cg.state = cg.BotState()
    cg.state.lane = lane
    assert cg.load_config()
    return cg.state


def _config_set(pairs) -> int:
    """cmd_config_set exits on errors and returns None on success."""
    try:
        cg.cmd_config_set(pairs)
    except SystemExit as e:
        return e.code
    return 0


# ── L1 identity ────────────────────────────────────────────────────────

def test_apply_lane_switches_paths_and_log_prefix():
    base_state, base_pid = cg.STATE_PATH, cg.PID_PATH
    cg._apply_lane(3)
    assert cg.state.lane == 3
    assert cg.STATE_PATH == cg.lane_path(base_state, 3) != base_state
    assert cg.PID_PATH == cg.lane_path(base_pid, 3) != base_pid
    rec = logging.LogRecord("cryptogames", logging.WARNING, __file__, 1, "hello", (), None)
    assert "[L3] hello" in cg._log_handler.format(rec)


def test_lane_log_prefix_still_masks_key():
    cg.state.api_key = "abcdefgh12345678EXAMPLE"
    cg._apply_lane(2)
    rec = logging.LogRecord("cryptogames", logging.WARNING, __file__, 1,
                            "url /v1/balance/doge/abcdefgh12345678EXAMPLE", (), None)
    out = cg._log_handler.format(rec)
    assert "[L2]" in out and "abcdefgh12345678EXAMPLE" not in out


def test_apply_lane_one_keeps_classic_paths():
    base_state, base_pid = cg.STATE_PATH, cg.PID_PATH
    fmt = cg._log_handler.formatter
    cg._apply_lane(None)
    cg._apply_lane(1)
    assert (cg.STATE_PATH, cg.PID_PATH) == (base_state, base_pid)
    assert cg._log_handler.formatter is fmt
    assert cg.state.lane == 1


@pytest.mark.parametrize("bad", [0, 100, -1])
def test_apply_lane_range(bad):
    with pytest.raises(ValueError):
        cg._apply_lane(bad)


def test_main_bad_lane_exits_2(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["cryptogames.py", "--status", "--lane", "100"])
    with pytest.raises(SystemExit) as e:
        cg.main()
    assert e.value.code == 2
    assert "--lane must be 1-99, got 100" in capsys.readouterr().out


def test_status_with_lane_reads_lane_state_file(monkeypatch):
    lane_state = cg.lane_path(cg.STATE_PATH, 2)
    seen = []
    monkeypatch.setattr(cg, "cmd_status", lambda: seen.append(cg.STATE_PATH))
    monkeypatch.setattr(sys, "argv", ["cryptogames.py", "--status", "--lane", "2"])
    cg.main()
    assert seen == [lane_state]


def test_stop_with_lane_uses_lane_pid(monkeypatch):
    Path(cg.lane_path(cg.PID_PATH, 2)).write_text("4343")
    kills = []
    monkeypatch.setattr(cg.os, "kill", lambda pid, sig: kills.append((pid, sig)))
    monkeypatch.setattr(sys, "argv", ["cryptogames.py", "--stop", "--lane", "2"])
    cg.main()
    assert kills == [(4343, signal.SIGTERM)]


def test_systemd_unit_per_lane():
    assert cg._service_unit() == "cryptogames"
    cg._apply_lane(4)
    assert cg._service_unit() == "cryptogames-lane@4"


# ── L2 DB ──────────────────────────────────────────────────────────────

def test_session_row_tagged_with_lane(cli_state):
    cli_state()
    cg.state.lane = 2
    sid = cg._db_start_session()
    with sqlite3.connect(cg.DB_PATH) as c:
        rows = dict(c.execute("SELECT id, lane FROM sessions").fetchall())
    assert rows[sid] == 2
    assert rows[sid - 1] == 1          # the fixture's lane-1 session


# ── L4 overrides / config ──────────────────────────────────────────────

def test_load_config_applies_lane_overrides(saved_config):
    _write_lanes(saved_config, count=3,
                 overrides={"2": {"max_loss": 1.5, "multiplier": 3.0,
                                  "streak_delay_loss": "3:2.5",
                                  "currency": "btc", "proxy": "socks5://x:1"}})
    s = _fresh_load(2)
    assert s.lanes_count == 3
    assert s.max_loss == 1.5 and s.multiplier == 3.0
    assert s.streak_delay_loss == (3, 2.5)
    assert s.currency == "btc" and s.proxy == "socks5://x:1"   # a lane may bet from its own account
    s1 = _fresh_load(1)
    assert s1.max_loss is None and s1.multiplier == 2.0


def test_save_config_keeps_lanes_block_and_lane_k_never_writes(saved_config):
    block = {"count": 2, "overrides": {"2": {"max_loss": 1.0}}}
    _write_lanes(saved_config, **block)
    s = _fresh_load(1)
    s.max_profit = 9.0
    cg.save_config()
    data = _raw(saved_config)
    assert data["lanes"] == block and data["max_profit"] == 9.0

    before = saved_config.read_text()
    s2 = _fresh_load(2)
    s2.max_profit = 1.0
    cg.save_config()
    assert saved_config.read_text() == before


def test_live_reload_merges_lane_overrides(saved_config):
    _fresh_load(2)
    _write_lanes(saved_config, count=2, overrides={"2": {"max_loss": 0.5, "bet_delay": 0.2}})
    applied = cg._reload_live_config()
    assert cg.state.max_loss == 0.5 and cg.state.bet_delay == 0.2
    assert set(applied) == {"max_loss", "bet_delay"}


def test_config_set_lanes_split_and_overrides(saved_config, monkeypatch, capsys):
    Path(cg.lane_path(cg.PID_PATH, 2)).write_text("4242")
    kills = []
    monkeypatch.setattr(cg.os, "kill", lambda pid, sig: kills.append((pid, sig)))
    rc = _config_set(["lanes=3", "lane_split=budget",
                      "lane2.maxloss=1.5", "lane3.mult=3", "lane3.sdloss=4:1"])
    assert rc == 0
    lanes = _raw(saved_config)["lanes"]
    assert cg.lanes_count(_raw(saved_config)) == 3 and lanes["split"] == "budget"
    assert lanes["items"]["2"]["overrides"] == {"max_loss": 1.5}
    ov3 = lanes["items"]["3"]["overrides"]
    assert ov3["multiplier"] == 3.0 and ov3["streak_delay_loss"] == "4:1"
    assert kills == [(4242, signal.SIGHUP)]            # only the touched running lane
    assert "Budget shares update when each lane restarts" in " ".join(capsys.readouterr().out.split())
    assert _raw(saved_config)["max_loss"] is None      # base config unchanged

    assert _config_set(["lane2.maxloss=default"]) == 0
    assert _raw(saved_config)["lanes"]["items"]["2"]["overrides"] == {}


def test_config_set_same_as_base_still_pins_override(saved_config):
    assert _config_set(["lane2.mult=2"]) == 0
    assert _raw(saved_config)["lanes"]["items"]["2"]["overrides"] == {"multiplier": 2.0}


@pytest.mark.parametrize("key", list(FORBIDDEN) + ["purgedays", "dbmode"])
def test_config_set_forbidden_lane_key_exits_2(saved_config, key):
    before = saved_config.read_text()
    assert _config_set([f"lane2.{key}=x"]) == 2
    assert saved_config.read_text() == before


@pytest.mark.parametrize("pairs", [["lanes=0"], ["lanes=11"], ["lanes=x"],
                                   ["lane1.maxloss=1"], ["lane100.maxloss=1"],
                                   ["lane_split=half"], ["lane2.lane_split=bet"],
                                   ["lane2.maxloss=abc"], ["lane2.nope=1"]])
def test_config_set_lane_syntax_refused(saved_config, pairs):
    before = saved_config.read_text()
    assert _config_set(pairs) == 2
    assert saved_config.read_text() == before


def test_config_set_base_signals_every_running_lane(saved_config, monkeypatch):
    _write_lanes(saved_config, count=5)
    Path(cg.PID_PATH).write_text("100")
    Path(cg.lane_path(cg.PID_PATH, 2)).write_text("200")
    Path(cg.lane_path(cg.PID_PATH, 5)).write_text("500")
    kills = []
    monkeypatch.setattr(cg.os, "kill", lambda pid, sig: kills.append((pid, sig)))
    assert _config_set(["maxloss=5"]) == 0
    assert [p for p, _ in kills] == [100, 200, 500]
    assert _raw(saved_config)["max_loss"] == 5.0
    assert _raw(saved_config)["lanes"] == {"count": 5}   # the base edit leaves lanes alone


def test_config_show_prints_lanes(saved_config, capsys, monkeypatch):
    monkeypatch.setattr(cg.console, "width", 200)
    _write_lanes(saved_config, count=3, split="both", overrides={"2": {"max_loss": 1.0}})
    cg.cmd_config_show()
    out = capsys.readouterr().out
    assert "Lanes: 3" in out and "split: both" in out
    assert "lane2 overrides: max_loss=1.00000000" in out


# ── v2.36.0 lane_split ─────────────────────────────────────────────────

def test_split_default_none_uses_full_bet(saved_config):
    _write_lanes(saved_config, count=4)
    s = _fresh_load(2)
    assert s.lane_split == "none" and s.base_bet == 0.01


@pytest.mark.parametrize("mode,expected", [("none", 0.01), ("budget", 0.01),
                                           ("bet", 0.0025), ("both", 0.0025)])
def test_split_modes_base_bet(saved_config, mode, expected):
    _write_lanes(saved_config, count=4, split=mode)
    s = _fresh_load(1)
    assert s.base_bet == expected and s.current_bet == expected


def test_split_bet_keeps_lane_base_bet_override(saved_config):
    _write_lanes(saved_config, count=4, split="bet", overrides={"2": {"base_bet": 0.007}})
    assert _fresh_load(2).base_bet == 0.007


def test_split_bet_rounding_to_zero_keeps_full(saved_config):
    data = _raw(saved_config)
    data["base_bet"] = 1e-8
    data["lanes"] = {"count": 4, "split": "bet"}
    saved_config.write_text(json.dumps(data))
    assert _fresh_load(1).base_bet == 1e-8


def test_split_bet_save_config_writes_full_bet(saved_config):
    _write_lanes(saved_config, count=2, split="bet")
    s = _fresh_load(1)
    assert s.base_bet == 0.005
    cg.save_config()
    assert _raw(saved_config)["base_bet"] == 0.01
    s.base_bet = 0.02                       # a real change is written as is
    cg.save_config()
    assert _raw(saved_config)["base_bet"] == 0.02


def test_split_basebet_pct_divided(cli_state):
    s = cli_state(basebet_pct=0.01, current_balance=10.0, lanes_count=4, split_lanes=4, lane_split="bet")
    assert cg._apply_basebet_pct()
    assert s.base_bet == pytest.approx(0.025)


def test_split_live_reload_no_spurious_base_bet_warning(saved_config, caplog):
    _write_lanes(saved_config, count=2, split="bet")
    _fresh_load(2)
    with caplog.at_level(logging.WARNING, logger="cryptogames"):
        cg._reload_live_config()
    assert "base_bet" not in caplog.text


# ── L3 split budget ────────────────────────────────────────────────────

def test_init_lane_budget():
    s = cg.state
    s.current_balance, s.lanes_count, s.split_lanes, s.lane_split = 9.0, 3, 3, "budget"
    cg._init_lane_budget()
    assert s.lane_share == pytest.approx(3.0)
    s.lane_split = "none"
    cg._init_lane_budget()
    assert s.lane_share is None
    s.lanes_count, s.split_lanes, s.lane_split = 1, 1, "both"
    cg._init_lane_budget()
    assert s.lane_share is None


def test_budget_stop_when_next_bet_exceeds_equity():
    s = cg.state
    s.lane_share, s.lane_run_profit, s.profit, s.current_bet = 1.0, -0.2, -0.3, 0.6
    stop, reason = cg.should_stop()
    assert stop and reason.startswith("Lane budget exceeded")
    # never a recurring restart, even with recurring on and no loss
    assert not should_restart(reason, 1.0, True, 5)


def test_budget_ok_within_equity_and_without_split():
    s = cg.state
    s.lane_share, s.lane_run_profit, s.profit, s.current_bet = 1.0, 0.0, -0.3, 0.7
    assert cg.should_stop() == (False, "")
    s.lane_share, s.current_bet = None, 1e9
    assert cg.should_stop() == (False, "")


def test_recurring_cycle_carries_lane_profit(cli_state):
    s = cli_state(lane_share=2.0)
    s.profit = 0.4
    s.running = True
    cg._reset_session_for_recurring(delay=0)
    assert s.lane_run_profit == pytest.approx(0.4) and s.profit == 0.0
    assert cg.lane_equity_now() == pytest.approx(2.4)


def test_risky_config_uses_lane_share_only_with_budget():
    s = cg.state
    s.strategy_key, s.loss_mult, s.base_bet = "2", 2.0, 1.0
    s.streak_reset_losses, s.max_loss = 3, None
    s.current_balance, s.lanes_count, s.split_lanes = 64.0, 4, 4

    def chain():
        return next(w for w in cg._check_risky_config() if w.startswith("Streak reset"))

    s.lane_split = "none"
    assert "balance covers a 6-loss chain" in chain()
    s.lane_split = "budget"
    assert "lane share covers a 4-loss chain" in chain()


def test_state_file_has_lane_fields(cli_state):
    s = cli_state(lane=2, lanes_count=2, split_lanes=2, lane_split="budget", lane_share=5.0)
    s.lane_run_profit = 0.5
    cg._save_state_file()
    d = _raw(cg.STATE_PATH)
    assert (d["lane"], d["lanes_count"], d["lane_split"]) == (2, 2, "budget")
    assert d["lane_share"] == 5.0 and d["lane_equity"] == pytest.approx(5.5)


# ── L5 start stagger ───────────────────────────────────────────────────

class _Started(Exception):
    pass


def _stub_start(monkeypatch, sleeps):
    sleeps.clear()
    monkeypatch.setattr(cg, "_load_and_connect", lambda: None)
    monkeypatch.setattr(cg, "_startup_purge", lambda: None)

    def started():
        raise _Started(list(sleeps))
    monkeypatch.setattr(cg, "_db_start_session", started)


def test_lane_start_stagger_and_budget(cli_state, monkeypatch, sleeps):
    cli_state(lanes_count=3, split_lanes=3, lane_split="budget")
    _stub_start(monkeypatch, sleeps)
    monkeypatch.setattr(sys, "argv", ["cryptogames.py", "--daemon", "--lane", "3"])
    with pytest.raises(_Started) as e:
        cg.main()
    assert e.value.args[0] == [4.0]
    assert cg.state.lane_share == pytest.approx(10.0 / 3)


def test_lane_one_does_not_stagger(cli_state, monkeypatch, sleeps):
    cli_state()
    _stub_start(monkeypatch, sleeps)
    monkeypatch.setattr(sys, "argv", ["cryptogames.py", "--daemon"])
    with pytest.raises(_Started) as e:
        cg.main()
    assert e.value.args[0] == []
    assert cg.state.lane_share is None


# ── lanes status ───────────────────────────────────────────────────────

def test_lanes_status_table(monkeypatch, capsys):
    monkeypatch.setattr(cg.console, "width", 160)
    Path(cg.CONFIG_PATH).write_text(json.dumps({"lanes": {"count": 3}}))
    Path(cg.STATE_PATH).write_text(json.dumps(
        {"pid": os.getpid(), "session_id": 1, "profit": 0.5, "bets_per_second": 2.0,
         "uptime_sec": 60, "run_uptime_sec": 120, "lane_equity": None}))
    Path(cg.lane_path(cg.STATE_PATH, 2)).write_text(json.dumps(
        {"pid": 999999, "session_id": 2, "profit": -0.25, "lane_equity": 4.75}))
    Path(cg.lane_path(cg.STATE_PATH, 3)).write_text("{bad")
    cg.cmd_lanes_status()
    out = capsys.readouterr().out
    assert "Parallel lanes" in out and "LIVE" in out and "STOPPED" in out
    assert "unreadable" in out and "4.75000000" in out
    assert "lanes live 1/3" in out and "2.0 bps" in out


def test_lanes_status_without_files(capsys):
    cg.cmd_lanes_status()
    assert "No lane state files" in capsys.readouterr().out


# ── L6 lane benchmark ──────────────────────────────────────────────────

class _FakeSession:
    """requests.Session stand-in: GETs go to the fake casino, proxies recorded."""
    made = []

    def __init__(self, casino):
        self.api = RequestsAPI(casino)
        self.proxies = {}
        _FakeSession.made.append(self)

    def get(self, url, timeout=None, **_):
        return self.api.get(url, timeout=timeout)


def test_benchmark_lanes_read_only_probe_and_recommendation(saved_config, fake_casino,
                                                            monkeypatch, capsys):
    monkeypatch.setattr(cg.console, "width", 200)
    _FakeSession.made = []
    monkeypatch.setattr(cg.requests, "Session", lambda: _FakeSession(fake_casino))
    data = _raw(saved_config)
    data["proxy"] = "socks5://127.0.0.1:1080"      # load_config applies it
    saved_config.write_text(json.dumps(data))
    monkeypatch.setattr(cg, "recommend_lanes", lambda base, rows: (base, rows) and 2)
    fake_casino.calls.clear()
    monkeypatch.setattr(sys, "argv", ["cryptogames.py", "--benchmark", "3", "--lanes", "3"])
    cg.main()
    out = capsys.readouterr().out
    # 1 + 2 + 3 clients × 3 GETs, all on the read-only balance URL, no bets
    assert len(fake_casino.calls) == 18
    assert {(m, u) for m, u, _ in fake_casino.calls} == {
        ("GET", f"{cg.API_BASE}/v1/balance/doge/test-key")}
    assert len(_FakeSession.made) == 6
    assert all(s.proxies.get("https") == "socks5://127.0.0.1:1080" for s in _FakeSession.made)
    assert "Concurrent clients" in out and "Recommended lanes: 2" in out
    assert "test-key" not in out


def test_bench_lanes_counts_429(monkeypatch):
    class _S:
        proxies = {}

        def get(self, url, timeout=None):
            return type("R", (), {"status_code": 429})()
    monkeypatch.setattr(cg.requests, "Session", _S)
    r = cg._bench_lanes(2, 2)
    assert r["total"] == 4 and r["ok"] == 0 and r["s429"] == 4


# ── two lanes on one account ───────────────────────────────────────────

class _LaneCasino(FakeCasino):
    """One lane's scripted outcomes on a balance shared by every lane."""

    def __init__(self, account, script):
        self.account = account
        super().__init__(balance=account["balance"], coin="doge", api_key="test-key",
                         script=script)

    @property
    def balance(self):
        return self.account["balance"]

    @balance.setter
    def balance(self, value):
        self.account["balance"] = value

    def handle(self, method, url, body):
        with self.account["lock"]:
            return super().handle(method, url, body)


def _load_lane_module(name, monkeypatch):
    spec = importlib.util.spec_from_file_location(name, cg.__file__)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, mod)
    spec.loader.exec_module(mod)
    return mod


def _setup_lane(mod, lane, casino, monkeypatch, **kw):
    for name in ("DB_PATH", "CONFIG_PATH"):
        monkeypatch.setattr(mod, name, getattr(cg, name))
    monkeypatch.setattr(mod, "_BASE_STATE_PATH", cg.STATE_PATH)
    monkeypatch.setattr(mod, "_BASE_PID_PATH", cg.PID_PATH)
    api = casino.requests_api()
    monkeypatch.setattr(mod._http_session, "get", api.get)
    monkeypatch.setattr(mod._http_session, "post", api.post)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    mod.state = mod.BotState()
    mod._apply_lane(lane)
    mod.init_db()
    s = mod.state
    s.api_key, s.currency, s.game, s.rule = "test-key", "doge", "dice", "under"
    s.multiplier, s.strategy, s.strategy_key = 2.0, "Flat Bet", "1"
    s.base_bet = s.current_bet = 0.01
    s.db_write_mode = "sync"
    s.lanes_count, s.split_lanes, s.lane_split = 2, 2, "budget"
    for k, v in kw.items():
        setattr(s, k, v)
    s.start_balance = s.current_balance = s.highest_balance = s.lowest_balance = casino.balance
    mod._init_lane_budget()
    s.session_id = mod._db_start_session()
    s.session_start = time.time()
    s.client_seed = mod._gen_client_seed()
    s.running = True
    return s


def test_two_lanes_in_threads_share_account(monkeypatch):
    account = {"balance": 10.0, "lock": threading.Lock()}
    c1 = _LaneCasino(account, ["win", "loss", "loss", "win", "loss"])
    c2 = _LaneCasino(account, ["loss", "loss", "win", "win"])
    m1 = _load_lane_module("cryptogames_lane_a", monkeypatch)
    m2 = _load_lane_module("cryptogames_lane_b", monkeypatch)
    try:
        s1 = _setup_lane(m1, 1, c1, monkeypatch, max_bets=5)
        # lane 2: Martingale 1.0 x2 on a 5.0 share; after two losses equity
        # is 2.0 and the next bet 4.0 → budget stop; recurring must not restart.
        s2 = _setup_lane(m2, 2, c2, monkeypatch, strategy="Martingale", strategy_key="2",
                         base_bet=1.0, current_bet=1.0, loss_mult=2.0, recurring=True,
                         recurring_delay=0)
        assert s1.lane_share == s2.lane_share == 5.0
        threads = [threading.Thread(target=m.betting_loop) for m in (m1, m2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert not any(t.is_alive() for t in threads)
    finally:
        for m in (m1, m2):
            m.state.running = False
            m.logger.removeHandler(m._log_handler)

    assert s1.total_bets == 5 and s1.status == "STOPPED: Max bets reached: 5"
    assert [b["amount"] for b in c1.bets] == [0.01] * 5            # flat, own chain
    assert [b["amount"] for b in c2.bets] == [1.0, 2.0]            # own Martingale chain
    assert s2.status.startswith("STOPPED: Lane budget exceeded (next bet 4.00000000")
    assert list(c2.script) == ["win", "win"]                       # stopped, no restart
    assert account["balance"] == pytest.approx(10.0 + c1.profit + c2.profit)

    # Each lane rotates its own ClientSeed: a fresh seed on every bet, and
    # no seed shared between the lanes.
    seeds1 = [b["seed"] for b in c1.bets]
    seeds2 = [b["seed"] for b in c2.bets]
    assert len(set(seeds1)) == 5 and len(set(seeds2)) == 2
    assert not set(seeds1) & set(seeds2)

    with sqlite3.connect(cg.DB_PATH) as c:
        rows = c.execute("SELECT lane, total_bets FROM sessions ORDER BY id").fetchall()
    assert rows == [(1, 5), (2, 2)]                                # one session per lane
