"""安全加固 CLI。

使用方法：
    python -m quant.apps.security check                    # 运行启动检查
    python -m quant.apps.security user create --username admin --role admin
    python -m quant.apps.security user list
    python -m quant.apps.security user show --user-id admin
    python -m quant.apps.security user role --user-id admin --role operator
    python -m quant.apps.security audit list
    python -m quant.apps.security audit query --action run_backtest
    python -m quant.apps.security audit stats
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from quant.core.security import (
    AuditLogger,
    Permission,
    RBACManager,
    Role,
    StartupGuard,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="安全加固工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # check 命令
    check_parser = subparsers.add_parser("check", help="运行启动检查")
    check_parser.add_argument("--config", help="配置文件路径")

    # user 命令
    user_parser = subparsers.add_parser("user", help="用户管理")
    user_subparsers = user_parser.add_subparsers(dest="subcommand", help="子命令")

    # user create
    user_create = user_subparsers.add_parser("create", help="创建用户")
    user_create.add_argument("--user-id", required=True, help="用户 ID")
    user_create.add_argument("--username", required=True, help="用户名")
    user_create.add_argument("--role", default="viewer", help="角色（admin/operator/viewer）")

    # user list
    user_list = user_subparsers.add_parser("list", help="列出用户")
    user_list.add_argument("--role", help="按角色过滤")

    # user show
    user_show = user_subparsers.add_parser("show", help="查看用户详情")
    user_show.add_argument("--user-id", required=True, help="用户 ID")

    # user role
    user_role = user_subparsers.add_parser("role", help="修改用户角色")
    user_role.add_argument("--user-id", required=True, help="用户 ID")
    user_role.add_argument("--role", required=True, help="新角色")

    # user deactivate
    user_deactivate = user_subparsers.add_parser("deactivate", help="停用用户")
    user_deactivate.add_argument("--user-id", required=True, help="用户 ID")

    # audit 命令
    audit_parser = subparsers.add_parser("audit", help="审计日志")
    audit_subparsers = audit_parser.add_subparsers(dest="subcommand", help="子命令")

    # audit list
    audit_list = audit_subparsers.add_parser("list", help="列出审计日志")
    audit_list.add_argument("--limit", type=int, default=20, help="返回条数")

    # audit query
    audit_query = audit_subparsers.add_parser("query", help="查询审计日志")
    audit_query.add_argument("--user-id", help="用户 ID")
    audit_query.add_argument("--action", help="操作类型")
    audit_query.add_argument("--limit", type=int, default=50, help="返回条数")

    # audit stats
    audit_stats = audit_subparsers.add_parser("stats", help="操作统计")

    return parser


def main() -> None:
    args = build_parser().parse_args()

    if not args.command:
        build_parser().print_help()
        return

    if args.command == "check":
        cmd_check(args)
    elif args.command == "user":
        cmd_user(args)
    elif args.command == "audit":
        cmd_audit(args)


def cmd_check(args):
    """运行启动检查。"""
    guard = StartupGuard()

    if args.config:
        from quant.core.security.startup_guard import load_config_from_yaml
        config = load_config_from_yaml(Path(args.config))
    else:
        from quant.core.security.startup_guard import load_config_from_env
        config = load_config_from_env()

    issues = guard.run_checks(config)
    report = guard.format_report(issues)
    print(report)


def cmd_user(args):
    """用户管理。"""
    manager = RBACManager()

    if not args.subcommand:
        print("请指定子命令：create / list / show / role / deactivate")
        return

    if args.subcommand == "create":
        role = Role(args.role)
        user = manager.create_user(
            user_id=args.user_id,
            username=args.username,
            role=role,
        )
        print(f"用户已创建: {user.username}")
        print(f"  用户 ID: {user.user_id}")
        print(f"  角色: {user.role.value}")

    elif args.subcommand == "list":
        role = Role(args.role) if args.role else None
        users = manager.list_users(role=role)

        if not users:
            print("暂无用户")
            return

        print(f"{'用户 ID':<15} {'用户名':<15} {'角色':<10} {'状态':<10} {'最后登录':<20}")
        print("-" * 70)

        for user in users:
            status = "活跃" if user.is_active else "停用"
            last_login = user.last_login[:19] if user.last_login else "从未登录"
            print(
                f"{user.user_id:<15} "
                f"{user.username:<15} "
                f"{user.role.value:<10} "
                f"{status:<10} "
                f"{last_login:<20}"
            )

    elif args.subcommand == "show":
        user = manager.get_user(args.user_id)
        if not user:
            print(f"错误: 用户 {args.user_id} 不存在")
            return

        print(f"用户 ID: {user.user_id}")
        print(f"用户名: {user.username}")
        print(f"角色: {user.role.value}")
        print(f"状态: {'活跃' if user.is_active else '停用'}")
        print(f"创建时间: {user.created_at}")
        print(f"最后登录: {user.last_login or '从未登录'}")

        # 显示权限
        permissions = manager.get_user_permissions(args.user_id)
        print()
        print("权限:")
        for perm in permissions:
            print(f"  - {perm.value}")

    elif args.subcommand == "role":
        role = Role(args.role)
        user = manager.update_user_role(args.user_id, role)
        if user:
            print(f"用户 {user.username} 角色已更新为: {user.role.value}")
        else:
            print(f"错误: 用户 {args.user_id} 不存在")

    elif args.subcommand == "deactivate":
        success = manager.deactivate_user(args.user_id)
        if success:
            print(f"用户 {args.user_id} 已停用")
        else:
            print(f"错误: 用户 {args.user_id} 不存在")


def cmd_audit(args):
    """审计日志。"""
    logger = AuditLogger()

    if not args.subcommand:
        print("请指定子命令：list / query / stats")
        return

    if args.subcommand == "list":
        entries = logger.get_recent_entries(limit=args.limit)

        if not entries:
            print("暂无审计日志")
            return

        print_audit_entries(entries)

    elif args.subcommand == "query":
        entries = logger.query(
            user_id=args.user_id,
            action=args.action,
            limit=args.limit,
        )

        if not entries:
            print("未找到匹配的审计日志")
            return

        print_audit_entries(entries)

    elif args.subcommand == "stats":
        stats = logger.get_action_stats()

        if not stats:
            print("暂无审计日志")
            return

        print("操作统计:")
        print("-" * 30)
        for action, count in stats.items():
            print(f"  {action}: {count}")


def print_audit_entries(entries):
    """打印审计日志。"""
    print(f"{'时间':<20} {'用户':<12} {'操作':<20} {'目标':<20} {'结果':<10}")
    print("-" * 82)

    for entry in entries:
        timestamp = entry.timestamp[:19]
        username = entry.username[:10]
        action = entry.action[:18]
        target = entry.target[:18]
        result = entry.result

        print(
            f"{timestamp:<20} "
            f"{username:<12} "
            f"{action:<20} "
            f"{target:<20} "
            f"{result:<10}"
        )


if __name__ == "__main__":
    main()
