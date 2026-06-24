"""策略生命周期管理 CLI。

使用方法：
    python -m quant.apps.lifecycle register --strategy momentum_rank --version v1
    python -m quant.apps.lifecycle list
    python -m quant.apps.lifecycle show --strategy momentum_rank
    python -m quant.apps.lifecycle transition --strategy momentum_rank --status paper
    python -m quant.apps.lifecycle review --strategy momentum_rank
    python -m quant.apps.lifecycle snapshots --strategy momentum_rank
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from quant.core.strategy.lifecycle import (
    StrategyLifecycleManager,
    StrategyStatus,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="策略生命周期管理")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # register 命令
    register_parser = subparsers.add_parser("register", help="注册新策略")
    register_parser.add_argument("--strategy", required=True, help="策略 ID")
    register_parser.add_argument("--version", default="v1", help="策略版本")
    register_parser.add_argument("--code-file", help="策略代码文件")
    register_parser.add_argument("--config", default="{}", help="策略配置（JSON）")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出策略")
    list_parser.add_argument("--status", help="按状态过滤")

    # show 命令
    show_parser = subparsers.add_parser("show", help="查看策略详情")
    show_parser.add_argument("--strategy", required=True, help="策略 ID")

    # transition 命令
    transition_parser = subparsers.add_parser("transition", help="转换策略状态")
    transition_parser.add_argument("--strategy", required=True, help="策略 ID")
    transition_parser.add_argument("--status", required=True, help="新状态")
    transition_parser.add_argument("--reason", default="", help="原因")

    # review 命令
    review_parser = subparsers.add_parser("review", help="审核策略")
    review_parser.add_argument("--strategy", required=True, help="策略 ID")
    review_parser.add_argument("--metrics", default="{}", help="回测指标（JSON）")

    # snapshots 命令
    snapshots_parser = subparsers.add_parser("snapshots", help="查看策略快照")
    snapshots_parser.add_argument("--strategy", required=True, help="策略 ID")

    return parser


def main() -> None:
    args = build_parser().parse_args()

    if not args.command:
        build_parser().print_help()
        return

    manager = StrategyLifecycleManager()

    if args.command == "register":
        cmd_register(manager, args)
    elif args.command == "list":
        cmd_list(manager, args)
    elif args.command == "show":
        cmd_show(manager, args)
    elif args.command == "transition":
        cmd_transition(manager, args)
    elif args.command == "review":
        cmd_review(manager, args)
    elif args.command == "snapshots":
        cmd_snapshots(manager, args)


def cmd_register(manager: StrategyLifecycleManager, args):
    """注册新策略。"""
    # 读取代码
    code = ""
    if args.code_file:
        with open(args.code_file, "r", encoding="utf-8") as f:
            code = f.read()
    else:
        # 使用默认代码
        code = f"class {args.strategy}Strategy: pass"

    config = json.loads(args.config)

    record = manager.register_strategy(
        strategy_id=args.strategy,
        version=args.version,
        code=code,
        config=config,
    )

    print(f"策略已注册: {args.strategy}")
    print(f"  版本: {args.version}")
    print(f"  状态: {record.status.value}")
    print(f"  快照 ID: {record.snapshot_id}")


def cmd_list(manager: StrategyLifecycleManager, args):
    """列出策略。"""
    status = StrategyStatus(args.status) if args.status else None
    strategies = manager.list_strategies(status=status)

    if not strategies:
        print("暂无策略记录")
        return

    print(f"{'策略 ID':<20} {'状态':<15} {'版本':<10} {'更新时间':<20}")
    print("-" * 65)

    for s in strategies:
        print(
            f"{s.strategy_id:<20} "
            f"{s.status.value:<15} "
            f"{s.current_version:<10} "
            f"{s.updated_at:<20}"
        )


def cmd_show(manager: StrategyLifecycleManager, args):
    """查看策略详情。"""
    record = manager.get_strategy(args.strategy)

    if not record:
        print(f"错误: 策略 {args.strategy} 不存在")
        return

    print(f"策略 ID: {record.strategy_id}")
    print(f"状态: {record.status.value}")
    print(f"版本: {record.current_version}")
    print(f"快照 ID: {record.snapshot_id}")
    print(f"审核 ID: {record.review_id or '无'}")
    print(f"模拟盘开始: {record.paper_start_date or '未开始'}")
    print(f"实盘开始: {record.production_start_date or '未开始'}")
    print(f"退役时间: {record.retired_date or '未退役'}")
    print(f"退役原因: {record.retired_reason or '-'}")
    print(f"创建时间: {record.created_at}")
    print(f"更新时间: {record.updated_at}")

    # 状态转换图
    print()
    print("可用状态转换:")
    from quant.core.strategy.lifecycle.lifecycle import VALID_TRANSITIONS
    valid = VALID_TRANSITIONS.get(record.status, [])
    if valid:
        for s in valid:
            print(f"  → {s.value}")
    else:
        print("  （终态，无法转换）")


def cmd_transition(manager: StrategyLifecycleManager, args):
    """转换策略状态。"""
    try:
        new_status = StrategyStatus(args.status)
        record = manager.transition(
            strategy_id=args.strategy,
            new_status=new_status,
            reason=args.reason,
        )
        print(f"状态已更新: {args.strategy}")
        print(f"  新状态: {record.status.value}")
    except ValueError as e:
        print(f"错误: {e}")


def cmd_review(manager: StrategyLifecycleManager, args):
    """审核策略。"""
    metrics = json.loads(args.metrics)

    review = manager.review_strategy(
        strategy_id=args.strategy,
        metrics=metrics,
    )

    print(f"审核完成: {args.strategy}")
    print(f"  审核 ID: {review.review_id}")
    print(f"  总分: {review.total_score}")
    print(f"  决策: {review.decision}")
    print()

    print("各项检查:")
    for r in review.criteria_results:
        status = "✓" if r.passed else "✗"
        print(f"  {status} {r.name}: {r.value} (阈值: {r.threshold}, 得分: {r.score})")


def cmd_snapshots(manager: StrategyLifecycleManager, args):
    """查看策略快照。"""
    snapshots = manager.snapshot_store.list_snapshots(strategy_id=args.strategy)

    if not snapshots:
        print(f"策略 {args.strategy} 暂无快照")
        return

    print(f"策略 {args.strategy} 的快照:")
    print()

    for snap in snapshots:
        print(f"快照 ID: {snap.snapshot_id}")
        print(f"  版本: {snap.strategy_version}")
        print(f"  代码哈希: {snap.code_hash}")
        print(f"  配置哈希: {snap.config_hash}")
        print(f"  因子集合: {snap.factor_set}")
        print(f"  创建时间: {snap.created_at}")
        if snap.backtest_summary:
            print(f"  回测摘要: {json.dumps(snap.backtest_summary, ensure_ascii=False)}")
        print()


if __name__ == "__main__":
    main()
