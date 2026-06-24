"""实验优化 CLI - 参数扫描、优化、实验记录。

使用方法：
    python -m quant.apps.experiment create --strategy momentum_rank --param-grid '{"top_pct": [0.1, 0.2, 0.3]}'
    python -m quant.apps.experiment run --experiment-id exp_001
    python -m quant.apps.experiment list
    python -m quant.apps.experiment show --experiment-id exp_001
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from quant.core.experiment.engine import ExperimentConfig, ExperimentEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="实验优化工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # create 命令
    create_parser = subparsers.add_parser("create", help="创建实验")
    create_parser.add_argument("--name", help="实验名称")
    create_parser.add_argument("--strategy", required=True, help="策略 ID")
    create_parser.add_argument("--param-grid", required=True, help="参数搜索空间（JSON）")
    create_parser.add_argument("--metric", default="sharpe", help="优化目标（默认 sharpe）")
    create_parser.add_argument("--start-date", default="2025-01-01", help="开始日期")
    create_parser.add_argument("--end-date", default="", help="结束日期")
    create_parser.add_argument("--rebalance", default="weekly", help="再平衡频率")
    create_parser.add_argument("--benchmark", default="000300.SH", help="基准代码")

    # run 命令
    run_parser = subparsers.add_parser("run", help="运行实验")
    run_parser.add_argument("--experiment-id", required=True, help="实验 ID")
    run_parser.add_argument("--method", choices=["grid", "random"], default="grid", help="搜索方法")
    run_parser.add_argument("--n-trials", type=int, default=50, help="随机搜索试验次数")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出实验")

    # show 命令
    show_parser = subparsers.add_parser("show", help="查看实验详情")
    show_parser.add_argument("--experiment-id", required=True, help="实验 ID")

    return parser


def main() -> None:
    args = build_parser().parse_args()

    if not args.command:
        build_parser().print_help()
        return

    engine = ExperimentEngine()

    if args.command == "create":
        cmd_create(engine, args)
    elif args.command == "run":
        cmd_run(engine, args)
    elif args.command == "list":
        cmd_list(engine, args)
    elif args.command == "show":
        cmd_show(engine, args)


def cmd_create(engine: ExperimentEngine, args):
    """创建实验。"""
    param_grid = json.loads(args.param_grid)

    experiment_id = f"exp_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    name = args.name or f"{args.strategy}_{args.metric}"

    config = ExperimentConfig(
        experiment_id=experiment_id,
        name=name,
        strategy_id=args.strategy,
        param_grid=param_grid,
        metric=args.metric,
        start_date=args.start_date,
        end_date=args.end_date,
        rebalance=args.rebalance,
        benchmark_code=args.benchmark,
    )

    # 保存配置（不运行）
    print(f"实验已创建: {experiment_id}")
    print(f"  名称: {name}")
    print(f"  策略: {args.strategy}")
    print(f"  参数空间: {json.dumps(param_grid, ensure_ascii=False)}")
    print(f"  优化目标: {args.metric}")
    print()
    print(f"运行命令: python -m quant.apps.experiment run --experiment-id {experiment_id}")


def cmd_run(engine: ExperimentEngine, args):
    """运行实验。"""
    # 从数据库获取实验配置
    experiment_data = engine.get_experiment(args.experiment_id)

    if experiment_data:
        # 使用已保存的配置
        config = ExperimentConfig(
            experiment_id=args.experiment_id,
            name=experiment_data["name"],
            strategy_id=experiment_data["strategy_id"],
            param_grid=experiment_data["param_grid"],
            metric=experiment_data["metric"],
        )
    else:
        # 提示用户先创建实验
        print(f"错误: 实验 {args.experiment_id} 不存在")
        print("请先创建实验: python -m quant.apps.experiment create ...")
        return

    print(f"开始运行实验: {args.experiment_id}")
    print(f"  策略: {config.strategy_id}")
    print(f"  方法: {args.method}")
    print()

    # 运行实验
    if args.method == "grid":
        result = engine.run_grid_search(config)
    else:
        result = engine.run_random_search(config, n_trials=args.n_trials)

    # 打印结果
    print_experiment_result(result)


def cmd_list(engine: ExperimentEngine, args):
    """列出实验。"""
    experiments = engine.list_experiments()

    if not experiments:
        print("暂无实验记录")
        return

    print(f"{'实验 ID':<25} {'名称':<20} {'策略':<15} {'状态':<10} {'创建时间':<20}")
    print("-" * 90)

    for exp in experiments:
        print(
            f"{exp['experiment_id']:<25} "
            f"{exp['name']:<20} "
            f"{exp['strategy_id']:<15} "
            f"{exp['status']:<10} "
            f"{exp['created_at']:<20}"
        )


def cmd_show(engine: ExperimentEngine, args):
    """查看实验详情。"""
    experiment = engine.get_experiment(args.experiment_id)

    if not experiment:
        print(f"错误: 实验 {args.experiment_id} 不存在")
        return

    print(f"实验 ID: {experiment['experiment_id']}")
    print(f"名称: {experiment['name']}")
    print(f"策略: {experiment['strategy_id']}")
    print(f"参数空间: {json.dumps(experiment['param_grid'], ensure_ascii=False)}")
    print(f"状态: {experiment['status']}")
    print(f"创建时间: {experiment['created_at']}")
    print()

    runs = experiment.get("runs", [])
    if not runs:
        print("暂无运行结果")
        return

    print(f"运行结果 ({len(runs)} 组):")
    print(f"{'排名':<5} {'参数':<40} {'Sharpe':<10} {'年化收益':<12} {'最大回撤':<12} {'总分':<10}")
    print("-" * 90)

    for run in runs[:20]:  # 只显示前 20 名
        params_str = json.dumps(run["params"], ensure_ascii=False)[:38]
        metrics = run.get("metrics", {})
        score = run.get("score", {})

        if "error" in metrics:
            print(f"{run['rank']:<5} {params_str:<40} {'ERROR':<10}")
        else:
            print(
                f"{run['rank']:<5} "
                f"{params_str:<40} "
                f"{metrics.get('sharpe', 0):<10.4f} "
                f"{metrics.get('annual_return', 0) * 100:<12.2f} "
                f"{metrics.get('max_drawdown', 0) * 100:<12.2f} "
                f"{score.get('total_score', 0):<10.2f}"
            )


def print_experiment_result(result):
    """打印实验结果。"""
    print()
    print("=" * 60)
    print(f"实验完成: {result.experiment_id}")
    print(f"  总运行次数: {result.total_runs}")
    print(f"  市场状态: {result.regime}")
    print()

    if result.best_run:
        best = result.best_run
        print("最优结果:")
        print(f"  排名: #{best.rank}")
        print(f"  参数: {json.dumps(best.params, ensure_ascii=False)}")
        print()

        metrics = best.metrics
        if "error" not in metrics:
            print("  指标:")
            print(f"    总收益: {metrics.get('total_return', 0) * 100:.2f}%")
            print(f"    年化收益: {metrics.get('annual_return', 0) * 100:.2f}%")
            print(f"    最大回撤: {metrics.get('max_drawdown', 0) * 100:.2f}%")
            print(f"    夏普比率: {metrics.get('sharpe', 0):.4f}")
            print(f"    超额收益: {metrics.get('excess_return', 0) * 100:.2f}%")
            print()

            if best.score:
                print(f"  综合评分: {best.score.get('total_score', 0):.2f}")
                print(f"  评级: {best.score.get('grade', '-')}")

    print("=" * 60)


if __name__ == "__main__":
    main()
