# WolfBet sync parity: CryptoGames

What this repo does compared to WolfBet CLI 2.16.0 to 2.37.2 and WolfBet TG v1.21.0, as of CryptoGames CLI 1.13.0 and TG 1.10.1 (2026-11-23).

- **Ported**: same behaviour as WolfBet.
- **Adapted**: same intent, changed to fit this casino's API (the note says how).
- **N/A**: the casino API cannot support it; the note gives the API reason.

Paths are relative to this repo. Run the tests with `APP_ENV=testing .venv-test/bin/python -m pytest cryptogames/tests -q` from the workspace root.

| WolfBet | Change | Status | Where | Test | Note |
|---|---|---|---|---|---|
| 2.16.0 | recurring restart, streak delays, `streakbet_loss`, `basebet_pct`, milestones | Ported | `cryptogames.py:1401`, `cryptogames.py:1353`, `cryptogames.py:1374`, `tg/engine.py:79` | `tests/test_wolfbet_sync_e10.py::test_recurring_keeps_run_milestone_and_total` | TG already had it |
| 2.16.0 | 429 Retry-After backoff | Ported | `cryptogames.py:1245` | `tests/test_wolfbet_sync_e0.py::test_cli_recovers_from_429_and_timeout` |  |
| 2.17.0 | API last / avg / peak / p50, on-target %, cycle, efficiency | Ported | `cryptogames.py:718`, `cryptogames.py:732`, `cryptogames.py:779` | `tests/test_wolfbet_sync_e5.py::test_record_api_ms_counters_and_on_target` | no rate-limit row: N/A, the API returns no quota headers |
| 2.18.0 | wizard Step 5b + preset keys | Ported | `cryptogames.py:3313` | `tests/test_wolfbet_sync_e3.py::test_preset_round_trip` |  |
| 2.19.0 | `T` tweak hotkey, `_apply_mutation` | Ported | `cryptogames.py:962`, `cryptogames.py:2522`, `tg/handlers.py:1241` | `tests/test_wolfbet_sync_e5.py::test_apply_mutation_fields` | no UUID clear: no server auto-bet; TG already had `/tweak` |
| 2.20.0 | exit summary, CSV / JSON export, `E` hotkey | Ported | `cryptogames.py:3706`, `cryptogames.py:3538`, `cryptogames.py:2495` | `tests/test_wolfbet_sync_e6.py::test_export_csv_shape_and_mode` |  |
| 2.21.0 | backtest / replay | Adapted | `cryptogames.py:3565`, `cryptogames.py:3645`, `cryptogames.py:3580` | `tests/test_wolfbet_sync_e6.py::test_backtest_is_deterministic_by_seed` | dice only, service house edge |
| 2.22.0 | `core/games.py` WolfBet game registry | N/A | - | - | WolfBet API game list; each service keeps its own game builders |
| 2.22.1 | `_check_risky_config` | Ported | `cryptogames.py:841` | `tests/test_wolfbet_sync_e5.py::test_risky_config_clean_for_safe_flat` |  |
| 2.23.0 | `--analytics` | Ported | `cryptogames.py:4733`, `tg/handlers.py:1809` | `tests/test_portability_v1.py::test_cmd_analytics_exists` | TG already had `/analytics` |
| 2.24.0 | `--pipeline N` | N/A | - | - | single-request bet API; concurrent bets break balance tracking |
| 2.25.0 | max-nonce recovery | N/A | - | - | WolfBet seed / nonce API; the service has no max-nonce error |
| 2.25.0 | `--config-show`, `--config-set`, `--version` | Ported | `cryptogames.py:5004`, `cryptogames.py:5069`, `cryptogames.py:5551` | `tests/test_wolfbet_sync_e10.py::test_config_set_scope` |  |
| 2.25.0 | monitor ROI / p99 | Ported | `cryptogames.py:725`, `cryptogames.py:3927` | `tests/test_wolfbet_sync_e5.py::test_cycle_p50_resists_outlier_p99_catches_it` |  |
| 2.25.1 - 2.25.2 | ctl subcommands, `--autostash` | Ported | `cgctl:1075`, `cgctl:782` | `tests/test_wolfbet_sync_e6.py::test_ctl_syntax` |  |
| 2.25.3 | `recurring_delay` | Ported | `cryptogames.py:159` | `tests/test_wolfbet_sync_e2.py::test_recurring_keeps_recurring_delay` | TG already had it (no cap) |
| 2.26.0 | proxy, `purge_days` + `--cleanup` | Ported | `cryptogames.py:22`, `cryptogames.py:5248`, `cryptogames.py:5267` | `tests/test_wolfbet_sync_e5.py::test_purge_days_default_clamp_off_alias` |  |
| 2.26.1 | `--benchmark`, `--diagnose` | Adapted | `cryptogames.py:5335`, `cryptogames.py:5410` | `tests/test_portability_v1.py::test_cmd_diagnose_exists` | probe = the service's read-only endpoint |
| 2.27.0 | async bet writer + PRAGMAs | Ported | `cryptogames.py:1944`, `cryptogames.py:2029` | `tests/test_wolfbet_sync_e5.py::test_writer_batches_land_and_stop_drains` | PRAGMAs were already there; TG already batched |
| 2.28.0 | helpers moved to `core/` | Adapted | `cryptogames.py:15` | `tests/test_portability_v1.py::test_tg_analytics_parses_date_window` | pure helpers live in casino-shared (`shared.core.*`) |
| 2.28.1 | monitor footer hints, systemd-aware stop | Ported | `cryptogames.py:3896`, `cryptogames.py:4417` | `tests/test_wolfbet_sync_e5.py::test_is_systemd_managed` |  |
| 2.28.2 | config persistence gap | Ported | `cryptogames.py:261` | `tests/test_wolfbet_sync_e10.py::test_run_profit_sums_sessions_and_bumps_persist` |  |
| 2.28.3 | SIGHUP live reload | Ported | `cryptogames.py:376`, `cryptogames.py:426` | `tests/test_wolfbet_sync_e10.py::test_live_reload_increment_off_ends_run` |  |
| 2.28.4 | uptime freezes in recurring pause | Ported | `cryptogames.py:657`, `tg/engine.py:109` | `tests/test_wolfbet_sync_e3.py::test_pause_freezes_uptime_and_reports_remaining` | TG already had it |
| 2.29.0 | profit increment restarts the auto cycle | N/A | - | - | no server auto-bet cycle; the bump already applies to the next bet |
| 2.30.0 | CFG row | Ported | `cryptogames.py:3798` | `tests/test_wolfbet_sync_e10.py::test_progress_row_uses_run_total` | pre-existing |
| 2.30.1 | persist `next_profit_milestone`, reset per cycle | Ported | `cryptogames.py:234`, `tg/engine.py:197` | `tests/test_wolfbet_sync_e10.py::test_recurring_keeps_run_milestone_and_total` | the CFG `Ms` segment now reads the persisted milestone |
| 2.30.2 | ctl update self-heal | Ported | `cgctl:1075` | `tests/test_wolfbet_sync_e5.py::test_apply_mutation_base_bet_updates_current_bet` |  |
| 2.30.3 - 2.30.5 | metric correctness, windowed cycle / efficiency | Ported | `cryptogames.py:746`, `cryptogames.py:779` | `tests/test_wolfbet_sync_e5.py::test_metric_helpers_empty` |  |
| wolfctl 3.7 - 3.8 | `doctor [--fix]`, `Nice=-5` | Ported | `cgctl:1127`, `install.sh:99` | `tests/test_wolfbet_sync_e7.py::test_doctor_warns_on_a_disabled_unit_and_loose_config` |  |
| 2.30.6 | `recurring_delay` cap 86400 + visible clamps | Ported | `cryptogames.py:16`, `tg/handlers.py:30` | `tests/test_wolfbet_sync_e2.py::test_recurring_delay_capped_at_stop` | CLI and TG |
| 2.30.7 | `Ms` per-window progress | Ported | `cryptogames.py:3818` | `tests/test_wolfbet_sync_e3.py::test_cfg_row_ms_window_rec_and_sr` |  |
| 2.30.8 | `bet_value` / 422 | N/A | - | - | WolfBet bet_value validation; the service has no such field |
| 2.30.9 | ctl `reset` / `archives`, `--stats --since / --until` | Ported | `cgctl:1128`, `cgctl:1130`, `cryptogames.py:5578` | `tests/test_wolfbet_sync_e7.py::test_reset_archives_and_never_deletes` |  |
| security 2026-11-15 | default web credentials refused, per-user web authz, WS `_connect_ro`, owner gate, `nan` / `inf` limits, pinned `ctl update`, admin secret rendering, API keys out of logs | Adapted | `web/config.py:12`, `web/bot_db.py:9`, `cryptogames.py:238` | `tests/test_security_hotfix.py::test_other_user_is_forbidden` | same intent, service code paths |
| security 2026-11-15 | service-specific guards | Ported | `cryptogames.py:238` | `tests/test_wolfbet_sync_e5.py::test_redact_masks_key` | API key redaction |
| 2.31.0 | date-range analytics | Ported | `cryptogames.py:4450` | `tests/test_wolfbet_sync_e3.py::test_cfg_row_ms_window_rec_and_sr` | TG already had it |
| 2.32.0 | streak reset | Ported | `cryptogames.py:17`, `tg/config.py:51` | `tests/test_wolfbet_sync_e2.py::test_streak_reset_fires_on_breaking_win_at_profit` | CLI and TG |
| 2.32.1 | insufficient balance is terminal on auto | Adapted | `cryptogames.py:599`, `tg/engine.py:164` | `tests/test_wolfbet_sync_e0.py::test_cli_insufficient_balance_stops` | terminal stop + chain-depth warning; mid-chain auto guard N/A (no server auto-bet) |
| 2.33.0 | time-of-day window fix | Ported | `cryptogames.py:53` | `tests/test_wolfbet_sync_e4.py::test_time_of_day_window_with_space` | CLI and TG |
| 2.33.1 | wins / losses per session | Ported | `cryptogames.py:2109` | `tests/test_wolfbet_sync_e4.py::test_wins_losses_per_session` |  |
| 2.34.0 | durations, time span, run time | Ported | `cryptogames.py:53` | `tests/test_wolfbet_sync_e4.py::test_time_span_vs_bet_time` |  |
| 2.35.0 | parallel lanes: `--lane K`, laneK paths, `[LK]` prefix | Ported | `cryptogames.py:123` | `tests/test_wolfbet_sync_e5_lanes.py::test_apply_lane_switches_paths_and_log_prefix` |  |
| 2.35.0 | `sessions.lane` column | Ported | `core/database.py:14` | `tests/test_wolfbet_sync_e4.py::test_init_db_adds_lane_to_old_db` | schema lives in casino-shared `SESSIONS_SCHEMA` |
| 2.35.0 | split budget, `Lane budget exceeded` loss stop | Ported | `cryptogames.py:1322`, `cryptogames.py:58` | `tests/test_wolfbet_sync_e5_lanes.py::test_init_lane_budget` |  |
| 2.35.0 | per-lane overrides, `config-set lanes=N` / `laneK.key` | Ported | `cryptogames.py:5193` | `tests/test_wolfbet_sync_e5_lanes.py::test_load_config_applies_lane_overrides` |  |
| 2.35.0 | lane start stagger | Ported | `cryptogames.py:5719` | `tests/test_wolfbet_sync_e5_lanes.py::test_lane_start_stagger_and_budget` |  |
| 2.35.0 | soft pacing from `x-ratelimit-*` headers | N/A | - | - | the service returns no quota headers; each lane keeps the 429 backoff |
| 2.35.0 | `/auto/start` cross-lane lock | N/A | - | - | no server auto-bet |
| 2.35.0 | `pipeline_depth` forbidden key | N/A | - | - | no pipeline |
| 2.35.0 | `--benchmark --lanes M` | Adapted | `cryptogames.py:5351` | `tests/test_wolfbet_sync_e5_lanes.py::test_benchmark_lanes_read_only_probe_and_recommendation` | read-only probe at 1..M concurrent clients |
| 2.35.0 | `--stats` / `--analytics --lane K`, analytics By lane | Ported | `cryptogames.py:4660` | `tests/test_wolfbet_sync_e4.py::test_analytics_by_lane_totals` |  |
| wolfctl 3.10 | ctl `lanes [N]`, all-lane start / stop / restart / update / reset | Ported | `cgctl:1109` | `tests/test_wolfbet_sync_e7.py::test_lanes_n_writes_config_and_enables_lane_units` |  |
| 2.35.0 | service-specific lanes | Adapted | `cryptogames.py:113` | `tests/test_wolfbet_sync_e3.py::test_client_seed_rotates_and_cryptorider_runs_across_cycles` | client seed rotation per the client's scope |
| 2.36.0 | `lane_split` none / budget / bet / both | Ported | `cryptogames.py:314`, `cryptogames.py:57` | `tests/test_wolfbet_sync_e5_lanes.py::test_config_set_lanes_split_and_overrides` | a divided bet below the service minimum stays full |
| wolfctl 3.11 | ctl `lanes N --split MODE` | Ported | `cgctl:196` | `tests/test_wolfbet_sync_e5_lanes.py::test_config_set_lanes_split_and_overrides` |  |
| 2.37.0 | `profit_increment_scope` / `piscope` session / run, run file, DB sum, resume bumps | Ported | `cryptogames.py:1600`, `cryptogames.py:1544`, `cryptogames.py:82` | `tests/test_wolfbet_sync_e10.py::test_stale_run_file_after_db_reset_starts_new_run` | CLI; TG adapted by request |
| 2.37.0 | status `Run Profit`, monitor `RunMs` | Ported | `cryptogames.py:4388`, `cryptogames.py:3818` | `tests/test_wolfbet_sync_e10.py::test_progress_row_uses_run_total` |  |
| 2.37.0 | `--run-reset`, ctl `run-reset`, `reset` clears run files | Ported | `cryptogames.py:1637`, `cgctl:1129`, `tg/handlers.py:1361` | `tests/test_wolfbet_sync_e10.py::test_run_reset_removes_files` |  |
| 2.37.0 | auto-UUID restart on bump | N/A | - | - | no server auto-bet; the bumped base applies to the next bet |
| 2.37.1 | UUID swap waits for non-negative profit and streak | N/A | - | `tests/test_wolfbet_sync_e8_regression.py::test_cli_bump_on_a_loss_keeps_betting_martingale` | no server auto-bet, UUID or mid-chain guard; proven by the regression test instead |
| 2.37.1 | `Stop reason` row + `DAEMON EXIT ... reason=` | Ported | `cryptogames.py:3726`, `cryptogames.py:5809` | `tests/test_wolfbet_sync_e6.py::test_summary_shows_the_stop_reason` |  |
| 2.37.1 | `install.sh` enables the CLI unit (boot only) | Ported | `install.sh:208` | `tests/test_wolfbet_sync_e7.py::test_lanes_n_writes_config_and_enables_lane_units` | lane units too; `doctor` flags a disabled unit |
| 2.37.2 | bumps belong to the base they were earned on | Ported | `cryptogames.py:1512`, `cryptogames.py:306` | `tests/test_wolfbet_sync_e10.py::test_live_base_change_zeroes_bumps_and_reanchors` | live base reload judged against the configured base; run file keeps `base` |
| TG v1.21.0 | TG run-wide increment, parity with CLI 2.37.0 | Adapted | `tg/config.py:49`, `tg/handlers.py:1361` | `tests/test_wolfbet_sync_e10.py::test_tg_new_run_at_start` | WolfBet TG lacked it; added by request following v1.21.0 |

## Known gaps

Found by the cross-service regression suite (`tests/test_wolfbet_sync_e8_regression.py`); recorded, not fixed here.

- CLI user pause (SIGUSR1 / `p`) does not freeze session uptime; the regression test is a strict xfail.
