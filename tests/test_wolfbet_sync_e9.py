"""Cryptogames CLI lane money split (CLI v1.11.0).

Mirrors WolfBet v2.36.0 (`lane_split`, `6174b96`). Most of it shipped in
1.10.0 and is tested in test_wolfbet_sync_e5_lanes.py (modes, override kept,
round-to-0, save keeps the full bet, basebet_pct divided, live reload,
config-set / config-show, chain warning). This file adds the cryptogames
adapt: the coin's MinimumBet (GET /v1/settings/{coin}) is read once at bot
start, and a split bet below it stays full (logged), for base_bet (start and
SIGHUP) and basebet_pct. Reference test: wolfbet/tests/test_phase10_lanes.py.

Run: APP_ENV=testing .venv-test/bin/python -m pytest cryptogames/tests -q
"""

import json
import logging
from pathlib import Path

import pytest

import cryptogames as cg


@pytest.fixture
def saved_config(cli_state, fake_casino):
    fake_casino.min_bet = 0.001
    cli_state(base_bet=0.003)               # 0.003 / 4 = 0.00075 < MinimumBet 0.001
    cg.state.running = False
    cg.save_config()
    return Path(cg.CONFIG_PATH)


def _write_lanes(path, base_bet=None, **lanes):
    data = json.loads(Path(path).read_text())
    data["lanes"] = lanes
    if base_bet is not None:
        data["base_bet"] = base_bet
    Path(path).write_text(json.dumps(data))


def _start(lane=1):
    """Fresh state, load config, then the start-time min-bet lookup."""
    cg.state = cg.BotState()
    cg.state.lane = lane
    assert cg.load_config()
    cg._load_min_bet()
    return cg.state


# ── min bet lookup ─────────────────────────────────────────────────────

def test_min_bet_read_from_coin_settings(saved_config):
    assert _start().min_bet == 0.001


def test_settings_failure_keeps_zero_and_split(saved_config, monkeypatch, caplog):
    _write_lanes(saved_config, count=4, split="bet")
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(cg, "api_get_settings", boom)
    with caplog.at_level(logging.WARNING, logger="cryptogames"):
        s = _start(2)
    assert s.min_bet == 0.0 and s.base_bet == pytest.approx(0.00075)
    assert "settings lookup failed" in caplog.text


# ── base_bet split vs MinimumBet ───────────────────────────────────────

@pytest.mark.parametrize("mode", ["bet", "both"])
def test_split_below_min_bet_keeps_full(saved_config, mode, caplog):
    _write_lanes(saved_config, count=4, split=mode)
    with caplog.at_level(logging.WARNING, logger="cryptogames"):
        s = _start(2)
    assert s.base_bet == 0.003 and s.current_bet == 0.003
    assert s.base_bet_split is None
    assert "below the minimum bet" in caplog.text


def test_split_at_or_above_min_bet_divides(saved_config, caplog):
    _write_lanes(saved_config, count=3, split="bet")         # 0.003 / 3 = 0.001
    with caplog.at_level(logging.WARNING, logger="cryptogames"):
        s = _start(1)
    assert s.base_bet == pytest.approx(0.001)
    assert "below the minimum bet" not in caplog.text


def test_below_min_full_bet_saved_unchanged(saved_config):
    _write_lanes(saved_config, count=4, split="bet")
    _start(1)
    cg.save_config()
    assert json.loads(saved_config.read_text())["base_bet"] == 0.003


def test_override_below_min_kept_as_is(saved_config):
    _write_lanes(saved_config, count=4, split="bet", overrides={"2": {"base_bet": 0.0005}})
    s = _start(2)
    assert s.base_bet == 0.0005 and s.base_bet_split is None


def test_live_reload_below_min_keeps_full_no_warning(saved_config, caplog):
    _write_lanes(saved_config, count=4, split="bet")
    s = _start(2)
    with caplog.at_level(logging.WARNING, logger="cryptogames"):
        applied = cg._reload_live_config()
    assert "base_bet" not in applied and s.base_bet == 0.003
    assert "base_bet changed" not in caplog.text


# ── basebet_pct split vs MinimumBet ────────────────────────────────────

def test_basebet_pct_below_min_keeps_full(cli_state, caplog):
    # 10 x 0.0003 = 0.003; / 4 = 0.00075 < 0.001
    s = cli_state(basebet_pct=0.0003, current_balance=10.0, lanes_count=4, split_lanes=4,
                  lane_split="both", min_bet=0.001)
    with caplog.at_level(logging.WARNING, logger="cryptogames"):
        assert cg._apply_basebet_pct()
    assert s.base_bet == pytest.approx(0.003) and s.current_bet == pytest.approx(0.003)
    assert "below the minimum bet" in caplog.text


def test_basebet_pct_above_min_divided(cli_state):
    s = cli_state(basebet_pct=0.001, current_balance=10.0, lanes_count=2, split_lanes=2,
                  lane_split="bet", min_bet=0.001)
    assert cg._apply_basebet_pct()
    assert s.base_bet == pytest.approx(0.005)


@pytest.mark.parametrize("mode", ["none", "budget"])
def test_basebet_pct_not_divided_without_bet_split(cli_state, mode):
    s = cli_state(basebet_pct=0.002, current_balance=10.0, lanes_count=2, split_lanes=2, lane_split=mode)
    assert cg._apply_basebet_pct()
    assert s.base_bet == pytest.approx(0.02)


# ── modes end to end ───────────────────────────────────────────────────

def test_none_default_full_bet_no_budget(saved_config):
    _write_lanes(saved_config, base_bet=0.01, count=2)
    s = _start(2)
    assert s.lane_split == "none" and s.base_bet == 0.01
    s.current_balance = 1.0
    cg._init_lane_budget()
    assert s.lane_share is None
    s.current_bet = 1e9
    assert cg.should_stop() == (False, "")


def test_both_splits_bet_and_budget(saved_config):
    _write_lanes(saved_config, base_bet=0.01, count=2, split="both")
    s = _start(2)
    assert s.base_bet == pytest.approx(0.005)
    s.current_balance = 4.0
    cg._init_lane_budget()
    assert s.lane_share == pytest.approx(2.0)
    s.current_bet = 2.5
    stop, reason = cg.should_stop()
    assert stop and reason.startswith("Lane budget exceeded")
