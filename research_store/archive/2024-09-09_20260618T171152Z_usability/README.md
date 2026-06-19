# Personal Quant System

V1 starts with a local, auditable research loop:

```text
data -> universe -> factors -> strategy -> portfolio -> risk -> backtest -> report
```

The current implementation is intentionally conservative. It does not connect to a broker
or place real orders. Broker execution, QMT integration, Redis, Grafana, and AI-assisted
research are reserved for later phases after the local loop is stable.

## Start Here

For day-to-day use, start with the simplified runner:

```powershell
python -m quant.apps.start
```

If Rust/Cargo is not installed yet, run the Python-only paper workflow first:

```powershell
python -m quant.apps.start daily
```

Check the latest state at any time:

```powershell
python -m quant.apps.start status
```

For a more detailed operator diagnosis:

```powershell
python -m quant.apps.start doctor
```

To generate a single local operator home page:

```powershell
python -m quant.apps.start home
```

To practice broker fill import safely with sample files:

```powershell
python -m quant.apps.start practice-fills
```

To import a real broker fill CSV and refresh execution reports:

```powershell
python -m quant.apps.start import-fills --source path\to\broker_fills.csv
```

To archive the latest reports with a manifest:

```powershell
python -m quant.apps.start snapshot
```

See [START_HERE.md](START_HERE.md) for the operator-friendly Chinese guide.

## Advanced Command Reference

The commands below are the underlying auditable workflow steps. They are useful for
debugging, replaying one stage, or validating a specific artifact, but they are not
the recommended first entrypoint.

```powershell
python scripts/generate_sample_data.py
python -m quant.apps.clean daily-bars --input research_store/sample/daily_bar.csv --output research_store/sample/daily_bar.cleaned.csv --config config/cleaning.yaml --report research_store/reports/data_cleaning.json --report-md research_store/reports/data_cleaning.md
cargo run --manifest-path rust_core/Cargo.toml -- --input research_store/sample/daily_bar.csv --output research_store/sample/daily_bar.rust.cleaned.csv --config config/cleaning.yaml --report research_store/reports/data_cleaning_rust.json --report-md research_store/reports/data_cleaning_rust.md
python -m quant.apps.collect --source csv --stocks research_store/sample/stocks.csv --bars research_store/sample/daily_bar.cleaned.csv --sqlite research_store/market_data.sqlite3
python -m quant.apps.quality --sqlite research_store/market_data.sqlite3 --output-json research_store/reports/data_quality.json --output-md research_store/reports/data_quality.md
python -m quant.apps.backtest --bars research_store/sample/daily_bar.cleaned.csv --stocks research_store/sample/stocks.csv --output research_store/reports/sample_backtest.json --output-md research_store/reports/sample_backtest.md
python -m quant.apps.backtest --bars research_store/sample/daily_bar.cleaned.csv --stocks research_store/sample/stocks.csv --benchmark-bars research_store/sample/benchmark_hs300.csv --benchmark-code hs300 --output research_store/reports/sample_backtest_hs300.json --output-md research_store/reports/sample_backtest_hs300.md
python -m quant.apps.backtest --sqlite research_store/market_data.sqlite3 --output research_store/reports/sqlite_backtest.json --output-md research_store/reports/sqlite_backtest.md
python -m quant.apps.compare backtest-paper --backtest research_store/reports/sqlite_backtest.json --paper-sqlite research_store/paper_trading.sqlite3 --trade-date 2024-09-09
python -m quant.apps.research --sqlite research_store/market_data.sqlite3 --factor momentum_60d --train-ratio 0.7 --output-dir research_store/reports/alpha
python -m quant.apps.research --sqlite research_store/market_data.sqlite3 --factor quality_score --train-ratio 0.7 --output-dir research_store/reports/alpha
python -m quant.apps.trader --bars research_store/sample/daily_bar.cleaned.csv --stocks research_store/sample/stocks.csv --research-report research_store/reports/alpha/momentum_60d_h5.md --output research_store/reports/paper_plan.json --apply-fills
python -m quant.apps.risk_guard export-orders --plan research_store/reports/paper_plan.json --output research_store/sample/risk_guard_orders.csv
python -m quant.apps.risk_guard write-control --output research_store/state/risk_guard_control.env --trade-mode normal --reason "default normal trading control"
cargo run --manifest-path rust_core/Cargo.toml -p risk_guard -- --orders research_store/sample/risk_guard_orders.csv --control-file research_store/state/risk_guard_control.env --output research_store/reports/risk_guard.json --output-md research_store/reports/risk_guard.md --audit-log research_store/reports/risk_guard_audit.jsonl
python -m quant.apps.broker dry-run --plan research_store/reports/paper_plan.json --risk-guard research_store/reports/risk_guard.json --output-json research_store/reports/broker_submission.json --output-md research_store/reports/broker_submission.md --no-console
python -m quant.apps.broker policy-create --mode DRY_RUN --adapter dry_run --output-json config/execution_policy.generated.json --output-md config/execution_policy.generated.md --no-console
python -m quant.apps.broker authorization --submission research_store/reports/broker_submission.json --policy config/execution_policy.generated.json --output-json research_store/reports/execution_authorization.json --output-md research_store/reports/execution_authorization.md --no-console
python -m quant.apps.broker adapter-contract --submission research_store/reports/broker_submission.json --authorization research_store/reports/execution_authorization.json --adapter dry_run --output-json research_store/reports/broker_adapter_contract.json --output-md research_store/reports/broker_adapter_contract.md --no-console
python -m quant.apps.broker live-rehearsal --submission research_store/reports/broker_submission.json --adapter qmt --policy config/execution_policy.generated.json --output-json research_store/reports/live_rehearsal.json --output-md research_store/reports/live_rehearsal.md --no-console
python -m quant.apps.broker manual-package --submission research_store/reports/broker_submission.json --order-ticket research_store/reports/manual_order_ticket.csv --fill-template research_store/reports/manual_fill_template.csv --output-json research_store/reports/manual_execution.json --output-md research_store/reports/manual_execution.md --no-console
python -m quant.apps.broker import-fills --order-ticket research_store/reports/manual_order_ticket.csv --source research_store/sample/broker_fills_sample.csv --output research_store/sample/manual_fill_template.imported.csv --report-json research_store/reports/manual_fill_import_sample.json --report-md research_store/reports/manual_fill_import_sample.md --validate --validation-json research_store/reports/manual_fill_validation_sample.json --validation-md research_store/reports/manual_fill_validation_sample.md --no-console
python -m quant.apps.broker manual-validate --order-ticket research_store/reports/manual_order_ticket.csv --fills research_store/reports/manual_fill_template.csv --output-json research_store/reports/manual_fill_validation.json --output-md research_store/reports/manual_fill_validation.md --no-console
python -m quant.apps.broker manual-reconcile --order-ticket research_store/reports/manual_order_ticket.csv --fills research_store/reports/manual_fill_template.csv --trade-date 2024-09-09 --output-json research_store/reports/manual_reconciliation.json --output-md research_store/reports/manual_reconciliation.md --no-console
python -m quant.apps.report execution --output-json research_store/reports/execution_day_end.json --output-md research_store/reports/execution_day_end.md --no-console
python -m quant.apps.broker refresh --no-console
python -m quant.apps.broker audit-report --output-json research_store/reports/execution_audit_report.json --output-md research_store/reports/execution_audit_report.md --no-console
python -m quant.apps.report execution-dashboard --output-html research_store/reports/execution_dashboard.html
Get-Content research_store/reports/execution_audit.jsonl -Tail 20
python -m quant.apps.trader --bars research_store/sample/daily_bar.cleaned.csv --stocks research_store/sample/stocks.csv --strategy quality_rank --research-report research_store/reports/alpha/quality_score_h5.md --output research_store/reports/paper_plan_quality.json --apply-fills
python -m quant.apps.trader --bars research_store/sample/daily_bar.cleaned.csv --stocks research_store/sample/stocks.csv --strategy quality_rank_trend --research-report research_store/reports/alpha/quality_score_h5.md --output research_store/reports/paper_plan_quality_trend.json --apply-fills
python -m quant.apps.strategies fingerprint --strategy quality_rank_trend --research-report research_store/reports/alpha/quality_score_h5.md --output-json research_store/reports/strategy_fingerprint_quality_trend.json --output-md research_store/reports/strategy_fingerprint_quality_trend.md --no-console
python -m quant.apps.strategies list --sqlite research_store/paper_trading.sqlite3 --output-json research_store/reports/strategy_registry.json --output-md research_store/reports/strategy_registry.md --no-console
python -m quant.apps.events trace --trace-id paper:momentum_rank:2024-09-09:000002.SZ:BUY --output-json research_store/reports/event_trace.json --output-md research_store/reports/event_trace.md --no-console
python -m quant.apps.reconcile --local-positions research_store/sample/local_positions.csv --broker-positions research_store/sample/broker_positions.csv --trade-date 2024-09-09
python -m quant.apps.reconcile --local-orders research_store/sample/local_orders.csv --broker-orders research_store/sample/broker_orders.csv --local-fills research_store/sample/local_fills.csv --broker-fills research_store/sample/broker_fills.csv --trade-date 2024-09-09 --output research_store/reports/trade_reconciliation.json --output-md research_store/reports/trade_reconciliation.md
python -m quant.apps.daily --config config/daily.yaml
python -m quant.apps.runs latest --sqlite research_store/paper_trading.sqlite3 --workflow daily
python -m quant.apps.report daily --summary research_store/reports/daily_summary.json --paper-sqlite research_store/paper_trading.sqlite3 --output-md research_store/reports/daily_report.md --output-html research_store/reports/daily_report.html
python -m quant.apps.notify daily --summary research_store/reports/daily_summary.json --report-md research_store/reports/daily_report.md --report-html research_store/reports/daily_report.html
python -m quant.apps.monitor history --summary research_store/reports/daily_summary.json --cleaning-report research_store/reports/data_cleaning.json --risk-guard-audit research_store/reports/risk_guard_audit.jsonl
python -m quant.apps.monitor status --history research_store/monitoring/daily_history.csv
python -m quant.apps.preflight check --monitor-status research_store/monitoring/status_summary.json --risk-guard research_store/reports/risk_guard.json --broker-submission research_store/reports/broker_submission.json --execution-policy config/execution_policy.generated.json --output-json research_store/reports/pretrade_gate.json --output-md research_store/reports/pretrade_gate.md --no-console
python -m quant.apps.monitor history --summary research_store/reports/daily_summary.json --cleaning-report research_store/reports/data_cleaning.json --risk-guard-audit research_store/reports/risk_guard_audit.jsonl --pretrade-gate research_store/reports/pretrade_gate.json
python -m quant.apps.monitor status --history research_store/monitoring/daily_history.csv
python -m quant.apps.monitor metrics --status-json research_store/monitoring/status_summary.json --history research_store/monitoring/daily_history.csv --output-prom research_store/monitoring/metrics.prom --output-json research_store/monitoring/metrics.json --grafana-dashboard research_store/monitoring/grafana_dashboard.json
python -m quant.apps.monitor alerts --status-json research_store/monitoring/status_summary.json --output-json research_store/monitoring/alerts.json --output-md research_store/monitoring/alerts.md --no-console
python -m quant.apps.monitor stability --history research_store/monitoring/daily_history.csv --target-days 20 --output-json research_store/monitoring/stability.json --output-md research_store/monitoring/stability.md --no-console
python -m quant.apps.monitor readiness --alerts research_store/monitoring/alerts.json --pretrade-gate research_store/reports/pretrade_gate.json --stability research_store/monitoring/stability.json --output-json research_store/monitoring/readiness.json --output-md research_store/monitoring/readiness.md --no-console
python -m quant.apps.monitor refresh --history research_store/monitoring/daily_history.csv --pretrade-gate research_store/reports/pretrade_gate.json
python -m quant.apps.monitor config-check --output-json research_store/monitoring/config_health.json --output-md research_store/monitoring/config_health.md --no-console
python -m quant.apps.monitor observation-plan --history research_store/monitoring/daily_history.csv --bars research_store/sample/daily_bar.cleaned.csv --target-days 20 --max-dates 5 --output-json research_store/monitoring/observation_plan.json --output-md research_store/monitoring/observation_plan.md --no-console
python -m quant.apps.monitor observe-run --plan research_store/monitoring/observation_plan.json --stocks research_store/sample/stocks.csv --bars research_store/sample/daily_bar.cleaned.csv --max-dates 5 --target-days 20
python -m quant.apps.schedule windows --time 17:30 --working-dir . --config config/daily.yaml
python -m quant.apps.schedule cron --time 17:30 --working-dir . --config config/daily.yaml
pytest
cargo build --manifest-path rust_core/Cargo.toml
```
