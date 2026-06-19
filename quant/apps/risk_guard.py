from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import UTC, datetime

import pandas as pd


ORDER_COLUMNS = [
    "order_id",
    "account_id",
    "strategy_id",
    "ts_code",
    "side",
    "quantity",
    "price",
    "target_weight",
    "trade_date",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare order intents for the Rust risk guard.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export = subparsers.add_parser("export-orders", help="Export paper plan order intents to CSV.")
    export.add_argument("--plan", required=True)
    export.add_argument("--output", default="research_store/sample/risk_guard_orders.csv")

    write_control = subparsers.add_parser("write-control", help="Write a local risk guard control file.")
    write_control.add_argument("--output", default="research_store/state/risk_guard_control.env")
    write_control.add_argument("--trade-mode", default="normal", choices=["normal", "sell_only", "halt"])
    write_control.add_argument("--max-order-amount", type=float, default=100_000.0)
    write_control.add_argument("--max-single-weight", type=float, default=0.10)
    write_control.add_argument("--max-total-buy-weight", type=float, default=0.95)
    write_control.add_argument("--daily-loss", type=float, default=0.0)
    write_control.add_argument("--max-daily-loss", type=float, default=0.05)
    write_control.add_argument("--trading-start", default="09:30")
    write_control.add_argument("--trading-end", default="15:00")
    write_control.add_argument("--now", default="14:30")
    write_control.add_argument("--reason", default="")

    show_control = subparsers.add_parser("show-control", help="Show a local risk guard control file.")
    show_control.add_argument("--control-file", default="research_store/state/risk_guard_control.env")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "export-orders":
        orders = load_order_intents(Path(args.plan))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        orders.to_csv(output, index=False)
        print(f"Wrote {len(orders)} order intents to {output}")
    if args.command == "write-control":
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        text = render_control_file(
            trade_mode=args.trade_mode,
            max_order_amount=args.max_order_amount,
            max_single_weight=args.max_single_weight,
            max_total_buy_weight=args.max_total_buy_weight,
            daily_loss=args.daily_loss,
            max_daily_loss=args.max_daily_loss,
            trading_start=args.trading_start,
            trading_end=args.trading_end,
            now=args.now,
            reason=args.reason,
        )
        output.write_text(text, encoding="utf-8")
        print(f"Wrote risk guard control file to {output}")
    if args.command == "show-control":
        control = read_control_file(Path(args.control_file))
        print(json.dumps(control, ensure_ascii=False, indent=2))


def load_order_intents(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_orders = payload.get("order_intents", [])
    if not isinstance(raw_orders, list):
        raise ValueError("paper plan order_intents must be a list")
    rows = []
    for raw_order in raw_orders:
        if not isinstance(raw_order, dict):
            raise ValueError("paper plan order_intents must contain objects")
        rows.append({column: raw_order.get(column, "") for column in ORDER_COLUMNS})
    frame = pd.DataFrame(rows, columns=ORDER_COLUMNS)
    if frame.empty:
        return frame
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="raise").astype(int)
    frame["price"] = pd.to_numeric(frame["price"], errors="raise").astype(float)
    frame["target_weight"] = pd.to_numeric(frame["target_weight"], errors="raise").astype(float)
    return frame


def render_control_file(
    *,
    trade_mode: str,
    max_order_amount: float,
    max_single_weight: float,
    max_total_buy_weight: float,
    daily_loss: float,
    max_daily_loss: float,
    trading_start: str,
    trading_end: str,
    now: str,
    reason: str = "",
    updated_at: str | None = None,
) -> str:
    timestamp = updated_at or datetime.now(UTC).isoformat()
    normalized_mode = trade_mode.strip().upper().replace("-", "_")
    lines = [
        "# Risk Guard control file",
        f"updated_at={timestamp}",
        f"trade_mode={normalized_mode}",
        f"max_order_amount={max_order_amount}",
        f"max_single_weight={max_single_weight}",
        f"max_total_buy_weight={max_total_buy_weight}",
        f"daily_loss={daily_loss}",
        f"max_daily_loss={max_daily_loss}",
        f"trading_start={trading_start}",
        f"trading_end={trading_end}",
        f"now={now}",
        f"reason={reason}",
    ]
    return "\n".join(lines) + "\n"


def read_control_file(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"risk guard control file not found: {path}")
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        separator = "=" if "=" in line else ":"
        if separator not in line:
            continue
        key, value = line.split(separator, 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


if __name__ == "__main__":
    main()
