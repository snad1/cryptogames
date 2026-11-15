"""WolfBet sync: cryptogames run-wide profit increment (CLI v1.12.0, TG v1.10.0).

Mirrors WolfBet CLI v2.37.0 (`profit_increment_scope` / `piscope`, `0b7e71a`).
Scope "run" measures the profit of every session since the run started, so a
large threshold is reachable with many short recurring cycles, and the bumps
survive a restart through a per-lane / per-user run file. WolfBet's TG has no
run scope, so the CLI rules apply per TG user, with one session at a time.
Reference test: wolfbet/tests/test_phase10b_run_increment.py.

Run: APP_ENV=testing .venv-test/bin/python -m pytest cryptogames/tests -q
"""

import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

import cryptogames as cg
from tg import handlers as h
from tg.database import load_user_config, save_user_config


def _arm(pi=0.001, pt=0.05, scope="run", **overrides):
    cg.state.profit_increment = pi
    cg.state.profit_threshold = pt
    cg.state.profit_increment_scope = scope
    for k, v in overrides.items():
        setattr(cg.state, k, v)
    return cg.state


def _sessions(rows):
    """Insert session rows: (profit, lane) pairs. Returns their ids."""
    conn = cg._db_conn()
    ids = []
    for profit, lane in rows:
        cur = conn.execute(
            "INSERT INTO sessions (started_at, currency, game, strategy, base_bet, "
            "multiplier, start_balance, lane, profit) VALUES (?,?,?,?,?,?,?,?,?)",
            (cg.datetime.now().isoformat(), "doge", "dice", "Flat Bet",
             0.01, 2.0, 10.0, lane, profit))
        ids.append(cur.lastrowid)
    conn.commit()
    conn.close()
    return ids


def _write_run(path, first_session, bumps=0, started_at="2026-11-15T00:00:00"):
    Path(path).write_text(json.dumps(
        {"first_session": first_session, "started_at": started_at, "bumps": bumps}))


# ── session scope stays as it was ──────────────────────────────────────
def test_session_scope_uses_session_profit(cli_state):
    cli_state(max_bets=1)
    _arm(scope="session", profit=0.05, next_profit_milestone=0.05)
    cg._check_profit_increment()
    assert cg.state.base_bet == pytest.approx(0.011)
    assert cg.state.next_profit_milestone == pytest.approx(0.10)
    assert cg.state.run_bumps == 0


def test_init_run_ends_any_run_in_session_scope(cli_state):
    cli_state(max_bets=1)
    _arm(scope="session")
    _write_run(cg.RUN_PATH, 1, bumps=3)
    cg._init_run()
    assert cg.state.run_first_session is None
    assert not Path(cg.RUN_PATH).exists()


# ── new run, DB total, persisted bumps ────────────────────────────────
def test_new_run_created_at_first_session(cli_state):
    cli_state(max_bets=1)
    _arm()
    cg._attach_run(cg.state.session_id)
    saved = json.loads(Path(cg.RUN_PATH).read_text())
    assert saved["first_session"] == cg.state.session_id
    assert saved["bumps"] == 0


def test_run_profit_sums_sessions_and_bumps_persist(cli_state):
    cli_state(max_bets=1)
    _arm()
    first, _ = _sessions([(0.03, 1), (0.02, 1)])
    _write_run(cg.RUN_PATH, first, bumps=0)
    cg._init_run()
    assert cg.state.run_first_session == first
    assert cg.state.run_profit_done == pytest.approx(0.05)
    # The run total carries the finished sessions into the bump.
    cg.state.profit = 0.02
    cg.state.next_profit_milestone = 0.05
    cg._check_profit_increment()
    assert cg.state.run_bumps == 1
    assert json.loads(Path(cg.RUN_PATH).read_text())["bumps"] == 1
    assert cg.state.base_bet == pytest.approx(0.011)


def test_resume_restores_bumps_on_base_bet(cli_state):
    cli_state(max_bets=1, base_bet=0.01)
    _arm()
    sids = _sessions([(0.02, 1), (0.02, 1)])
    _write_run(cg.RUN_PATH, sids[0], bumps=2)
    cg._init_run()
    assert cg.state.base_bet == pytest.approx(0.012)
    assert cg.state.current_bet == pytest.approx(0.012)
    assert cg.state.next_profit_milestone == pytest.approx(0.15)


def test_stale_run_file_after_db_reset_starts_new_run(cli_state, caplog):
    cli_state(max_bets=1)
    _arm()
    _write_run(cg.RUN_PATH, 999, bumps=4)
    with caplog.at_level(logging.WARNING, logger="cryptogames"):
        cg._init_run()
    assert cg.state.run_first_session is None
    assert cg.state.run_bumps == 0
    assert "past the stats DB" in caplog.text


def test_lane_run_file_and_filter(cli_state):
    cli_state(max_bets=1)
    cg.state.lane = 2
    _arm()
    sids = _sessions([(0.02, 1), (0.04, 2)])
    _write_run(cg.run_path(cg.RUN_PATH, 2), sids[1], bumps=1)
    cg._init_run()
    assert cg.state.run_first_session == sids[1]
    assert cg.state.run_profit_done == pytest.approx(0.04)   # lane 2 only
    assert Path(cg.run_path(cg.RUN_PATH, 2)).exists()


# ── recurring cycle keeps the milestone in run scope ──────────────────
def test_recurring_keeps_run_milestone_and_total(cli_state):
    cli_state(max_bets=1)
    _arm(next_profit_milestone=0.10)
    cg.state.profit = 0.03
    cg._reset_session_for_recurring(0)
    assert cg.state.run_profit_done == pytest.approx(0.03)
    assert cg.state.next_profit_milestone == pytest.approx(0.10)


def test_recurring_resets_milestone_in_session_scope(cli_state):
    cli_state(max_bets=1)
    _arm(scope="session", next_profit_milestone=0.10)
    cg.state.profit = 0.03
    cg._reset_session_for_recurring(0)
    assert cg.state.next_profit_milestone == pytest.approx(0.05)


# ── config: scope + off values ────────────────────────────────────────
def _config_set(pairs):
    try:
        cg.cmd_config_set(pairs)
    except SystemExit as e:
        return e.code
    return 0


def test_config_set_scope(cli_state):
    cli_state(max_bets=1)
    cg.state.running = False
    cg.save_config()
    assert _config_set(["piscope=run"]) == 0
    assert cg.state.profit_increment_scope == "run"
    assert json.loads(Path(cg.CONFIG_PATH).read_text())["profit_increment_scope"] == "run"


def test_config_set_bad_scope_exits_2(cli_state):
    cli_state(max_bets=1)
    cg.state.running = False
    cg.save_config()
    assert _config_set(["piscope=weekly"]) == 2
    assert cg.state.profit_increment_scope == "session"


@pytest.mark.parametrize("key,val", [
    ("profit_increment", "0"), ("profit_increment", 0.0), ("profit_increment", "none"),
    ("profit_threshold", "0.0"), ("profit_threshold", 0.0), ("profit_threshold", "off"),
])
def test_mutation_zero_means_off(cli_state, key, val):
    cli_state(max_bets=1)
    _arm()
    cg._apply_mutation({key: val})
    assert getattr(cg.state, key) is None


# ── off / on at start and on live reload ─────────────────────────────
def test_init_run_off_removes_run_file(cli_state):
    cli_state(max_bets=1)
    _arm(pi=0)
    _write_run(cg.RUN_PATH, 1, bumps=2)
    cg._init_run()
    assert not Path(cg.RUN_PATH).exists()
    assert cg.state.run_first_session is None


def test_live_reload_increment_off_ends_run(cli_state):
    cli_state(max_bets=1)
    _arm()
    cg._attach_run(cg.state.session_id)
    cg.state.profit_increment = None
    cg._apply_increment_side_effects({"profit_increment": (0.001, None)})
    assert cg.state.run_first_session is None
    assert not Path(cg.RUN_PATH).exists()


def test_live_reload_increment_on_starts_run(cli_state):
    cli_state(max_bets=1)
    _arm(pi=None)
    cg.state.profit_increment = 0.001          # what the reload applied
    cg._apply_increment_side_effects({"profit_increment": (None, 0.001)})
    assert cg.state.run_first_session == cg.state.session_id
    assert Path(cg.RUN_PATH).exists()


# ── the bump never touches the DB ─────────────────────────────────────
def test_bump_does_no_db_query(cli_state, monkeypatch):
    cli_state(max_bets=1)
    _arm(profit=0.05, next_profit_milestone=0.05, run_profit_done=0.0)
    def boom():
        raise AssertionError("DB query from the bet path")
    monkeypatch.setattr(cg, "_db_conn", boom)
    cg._check_profit_increment()
    assert cg.state.base_bet == pytest.approx(0.011)


# ── reset + display ───────────────────────────────────────────────────
def test_run_reset_removes_files(cli_state):
    cli_state(max_bets=1)
    base = Path(cg.RUN_PATH)
    _write_run(base, 1)
    _write_run(cg.run_path(cg.RUN_PATH, 2), 2)
    cg.cmd_run_reset()
    assert not base.exists()
    assert not Path(cg.run_path(cg.RUN_PATH, 2)).exists()


def test_progress_row_uses_run_total(cli_state):
    cli_state(max_bets=1)
    row = cg._build_config_progress_row({
        "profit_increment": 0.001, "profit_threshold": 0.05,
        "profit_increment_scope": "run", "profit": 0.01,
        "run_profit_total": 0.05, "next_profit_milestone": 0.10,
    })
    assert "RunMs" in row and "0.00000000/0.05000000" in row


def test_state_file_carries_run_keys(cli_state):
    cli_state(max_bets=1)
    _arm()
    cg._attach_run(cg.state.session_id)
    cg._save_state_file()
    data = json.loads(Path(cg.STATE_PATH).read_text())
    assert data["profit_increment_scope"] == "run"
    assert data["run_first_session"] == cg.state.session_id
    assert data["run_bumps"] == 0
    assert data["run_profit_total"] == pytest.approx(0.0)


# ── TG: run file, resume, snapshot, /set, /tweak, /runreset ──────────
def _update(uid, replies):
    async def reply_text(text, **k):
        replies.append(text)
    return SimpleNamespace(effective_user=SimpleNamespace(id=uid),
                           message=SimpleNamespace(reply_text=reply_text))


def _cmd(fn, uid, *args):
    replies = []
    asyncio.run(fn(_update(uid, replies), SimpleNamespace(args=list(args))))
    return replies


def _tg_run_file(engine):
    return Path(engine.db_path).parent / "run.json"


def _start_sid(engine):
    """Open a real session row so the run-file staleness check has an id."""
    from core.database import init_db, migrate_db
    init_db(engine.db_path)
    migrate_db(engine.db_path)
    engine.start_balance = 10.0
    engine.session_id = engine._db_start_session()
    return engine.session_id


def test_tg_new_run_at_start(tg_engine_factory, run_tg):
    e = tg_engine_factory(
        profit_increment=0.001, profit_threshold=0.05, profit_increment_scope="run")
    run_tg(e)
    assert e.run_first_session == e.session_id
    saved = json.loads(_tg_run_file(e).read_text())
    assert saved["first_session"] == e.session_id


def test_tg_resume_restores_bumps(tg_engine_factory):
    e = tg_engine_factory(
        base_bet=0.01, profit_increment=0.001, profit_threshold=0.05,
        profit_increment_scope="run")
    _tg_run_file(e).write_text(json.dumps(
        {"first_session": 1, "started_at": "2026-11-15T00:00:00", "bumps": 2}))
    e._init_run()
    assert e.base_bet == pytest.approx(0.012)
    assert e.next_profit_milestone == pytest.approx(0.15)


def test_tg_basebet_pct_resume_adds_no_bumps(tg_engine_factory):
    e = tg_engine_factory(
        base_bet=0.01, basebet_pct=0.01, profit_increment=0.001,
        profit_threshold=0.05, profit_increment_scope="run")
    _tg_run_file(e).write_text(json.dumps(
        {"first_session": 1, "started_at": "2026-11-15T00:00:00", "bumps": 2}))
    e._init_run()
    assert e.base_bet == pytest.approx(0.01)      # the balance rule owns it
    assert e.run_bumps == 2


def test_tg_run_scope_bumps_on_run_total(tg_engine_factory):
    e = tg_engine_factory(
        profit_increment=0.001, profit_threshold=0.05, profit_increment_scope="run")
    e.run_first_session = 1
    e._run_base_origin = e.base_bet
    e._run_others = 0.04
    e.profit = 0.02
    e.next_profit_milestone = 0.05
    e._check_profit_increment()
    assert e.base_bet == pytest.approx(0.011)
    assert e.run_bumps == 1
    assert e.next_profit_milestone == pytest.approx(0.10)


def test_tg_second_slot_joins_the_run(tg_engine_factory):
    first = tg_engine_factory(
        profit_increment=0.001, profit_threshold=0.05, profit_increment_scope="run")
    first.session_id = _start_sid(first)
    first._attach_run(first.session_id)
    second = tg_engine_factory(
        profit_increment=0.001, profit_threshold=0.05, profit_increment_scope="run")
    second.session_id = _start_sid(second)
    second._attach_run(second.session_id)
    assert second.run_first_session == first.session_id   # one run per user
    assert second.run_bumps == 0


def test_tg_refresh_picks_up_sibling_bumps(tg_engine_factory):
    a = tg_engine_factory(
        profit_increment=0.001, profit_threshold=0.05, profit_increment_scope="run")
    a.session_id = _start_sid(a)
    a._run_base_origin = a.base_bet
    a._attach_run(a.session_id)
    b = tg_engine_factory(
        profit_increment=0.001, profit_threshold=0.05, profit_increment_scope="run")
    b.session_id = _start_sid(b)
    b._run_base_origin = b.base_bet
    b._attach_run(b.session_id)

    a.run_bumps = 2                             # slot A made two bumps
    a._save_run()
    b._refresh_run()
    assert b.run_bumps == 2
    assert b.base_bet == pytest.approx(0.012)


def test_tg_snapshot_roundtrip(tg_engine_factory):
    e = tg_engine_factory(
        profit_increment=0.001, profit_threshold=0.05, profit_increment_scope="run")
    e.run_first_session, e.run_bumps, e.run_since = 7, 2, "2026-11-15T00:00:00"
    e._run_base_origin = 0.01
    e.session_id = 7
    snap = e.snapshot_state()
    other = tg_engine_factory()
    other.restore_state(snap)
    assert (other.run_first_session, other.run_bumps) == (7, 2)
    assert other._run_base_origin == pytest.approx(0.01)


def test_tg_set_scope_and_validation():
    r = _cmd(h.cmd_set, 21, "piscope", "run")
    assert load_user_config(21)["profit_increment_scope"] == "run"
    assert "next start" in r[0]
    r = _cmd(h.cmd_set, 22, "piscope", "weekly")
    assert "piscope session" in r[0]
    assert load_user_config(22).get("profit_increment_scope") != "weekly"


@pytest.mark.parametrize("value", ["0", "0.0", "off", "none"])
def test_tg_set_increment_zero_means_off(value):
    save_user_config(23, {"profit_increment": 0.001})
    _cmd(h.cmd_set, 23, "pi", value)
    assert load_user_config(23)["profit_increment"] is None


def test_tg_tweak_pi_zero_ends_run(tg_engine_factory, monkeypatch):
    uid = 24
    e = tg_engine_factory(
        profit_increment=0.001, profit_threshold=0.05, profit_increment_scope="run")
    e.session_id = 3
    e._attach_run(3)
    monkeypatch.setitem(h.active_engines, uid, {1: e})
    e.running = True
    _cmd(h.cmd_tweak, uid, "pi", "0")
    assert e.profit_increment is None
    assert e.run_first_session is None
    assert not _tg_run_file(e).exists()


def test_tg_runreset_refuses_while_running(tg_engine_factory, monkeypatch):
    from tg.database import user_db_path
    uid = 25
    e = tg_engine_factory(
        profit_increment=0.001, profit_threshold=0.05, profit_increment_scope="run")
    e.session_id = _start_sid(e)
    e._attach_run(e.session_id)
    run_path = Path(user_db_path(uid)).parent / "run.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(_tg_run_file(e).read_text())
    monkeypatch.setitem(h.active_engines, uid, {1: e})
    e.running = True
    r = _cmd(h.cmd_runreset, uid)
    assert "Stop your sessions first" in r[0]
    assert run_path.exists()
    monkeypatch.setitem(h.active_engines, uid, {})
    r = _cmd(h.cmd_runreset, uid)
    assert "Run total reset" in r[0]
    assert not run_path.exists()


def test_tg_status_shows_run_profit_line(tg_engine_factory):
    e = tg_engine_factory(
        profit_increment=0.001, profit_threshold=0.05, profit_increment_scope="run")
    e.run_first_session, e.run_bumps, e._run_others = 5, 1, 0.06
    text = asyncio.run(_status_text(e))
    assert "Run Profit" in text and "1 bump(s)" in text


async def _status_text(engine):
    from tg.formatter import format_status
    return format_status(engine.get_status())
