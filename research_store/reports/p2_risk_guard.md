# P2 Risk Guard Progress

| Item | Status | Evidence |
| --- | --- | --- |
| Rust Risk Guard CLI | DONE | `rust_core/crates/risk_guard` |
| Max order amount | DONE | `--max-order-amount`, default `100000` |
| Max single weight | DONE | `--max-single-weight`, default `0.10` |
| Max total buy weight | DONE | `--max-total-buy-weight`, default `0.95` |
| Trading window guard | DONE | `--trading-start`, `--trading-end`, `--now` |
| Duplicate order guard | DONE | default duplicate `order_id` rejection |
| Kill switch | DONE | `--trade-mode halt` rejects every order |
| Sell-only lock | DONE | `--trade-mode sell_only` rejects buy orders and allows sells |
| Daily loss lock | DONE | `--daily-loss` and `--max-daily-loss` lock buy orders after loss threshold |
| Account control file | DONE | `research_store/state/risk_guard_control.env` drives Rust Risk Guard policy |
| Audit report | DONE | `research_store/reports/risk_guard.json`, `research_store/reports/risk_guard.md` |
| Append-only audit log | DONE | `research_store/reports/risk_guard_audit.jsonl` |
| Monitoring integration | DONE | `research_store/monitoring/status_summary.md` shows latest Risk Guard and Pre-Trade Gate status |
| Observability export | DONE | `research_store/monitoring/metrics.prom`, `metrics.json`, and `grafana_dashboard.json` |
| Local alert evaluation | DONE | `research_store/monitoring/alerts.md` shows local alert rule results |
| Stability observation | DONE | `research_store/monitoring/stability.md` tracks 20-day paper trading readiness |
| Readiness report | DONE | `research_store/monitoring/readiness.md` separates paper readiness from live readiness |
| One-command monitor refresh | DONE | `python -m quant.apps.monitor refresh` regenerates derived monitoring artifacts |
| Observation plan | DONE | `research_store/monitoring/observation_plan.md` recommends next paper observation dates |
| Observation runner | DONE | `python -m quant.apps.monitor observe-run` advances recommended paper observation dates and upserts monitoring history |
| Broker dry-run gate | DONE | `research_store/reports/broker_submission.md` is generated only after Risk Guard allows |
| Broker adapter contract | DONE | `research_store/reports/broker_adapter_contract.md` validates authorization, mode/adapter scope, order schema, uniqueness, and dry-run/live separation before adapter submission |
| Execution policy generator | DONE | `python -m quant.apps.broker policy-create` creates auditable policy JSON/Markdown and requires approval scope for non-dry-run modes |
| Execution authorization gate | DONE | `research_store/reports/execution_authorization.md` and `config/execution_policy.example.json` keep live execution behind explicit approval |
| Live execution rehearsal | DONE | `research_store/reports/live_rehearsal.md` proves LIVE-shaped submissions stay blocked without a matching approval policy |
| Manual execution package | DONE | `research_store/reports/manual_order_ticket.csv` and `manual_fill_template.csv` provide an auditable no-QMT handoff |
| Manual fill import | DONE | `python -m quant.apps.broker import-fills` converts broker/exported fill CSV rows into the manual fill template schema and can immediately run strict validation |
| Manual fill validation | DONE | `python -m quant.apps.broker manual-validate` checks filled CSV completeness and amount consistency |
| Manual fill reconciliation | DONE | `python -m quant.apps.broker manual-reconcile` converts manual fills into reconciliation artifacts and SQLite audit records |
| Execution day-end package | DONE | `research_store/reports/execution_day_end.md` summarizes plan, risk, authorization, handoff, gate, fills, reconciliation, and readiness |
| Execution audit JSONL | DONE | `research_store/reports/execution_audit.jsonl` appends authorization, manual package, validation, reconciliation, and day-end events |
| Execution audit report | DONE | `research_store/reports/execution_audit_report.md` summarizes the latest refresh cycle from append-only execution audit events |
| Execution dashboard | DONE | `research_store/reports/execution_dashboard.html` combines day-end, config health, readiness, and latest audit cycle into one local HTML view |
| One-command execution refresh | DONE | `python -m quant.apps.broker refresh` refreshes authorization, broker adapter contract, manual validation, reconciliation state, day-end report, config health, audit events, audit report, and execution dashboard |
| Config health check | DONE | `research_store/monitoring/config_health.md` validates local configs, CSV schemas, risk control, execution policy, and execution artifacts |
| Pre-trade gate | DONE | `research_store/reports/pretrade_gate.md` blocks when monitor, Risk Guard, or broker submission is unsafe |

The guard is intentionally offline and conservative. It validates exported order intents before any future broker adapter or QMT bridge is allowed to submit them.
