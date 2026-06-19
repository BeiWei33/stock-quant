from __future__ import annotations

import html
import json
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from quant.apps import start


ROOT = Path(__file__).resolve().parents[3]
RUN_DIR = ROOT / "research_store/web_runs"
UPLOAD_DIR = ROOT / "research_store/web_uploads"


@dataclass(frozen=True)
class WebRunResult:
    run_id: str
    action: str
    status: str
    return_code: int
    command: list[str]
    started_at: str
    ended_at: str
    stdout: str
    stderr: str
    log_path: str
    json_path: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Command runner
# ---------------------------------------------------------------------------


def run_command(action: str, command: list[str]) -> WebRunResult:
    import random
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"_{random.randrange(1000,9999)}"
    started_at = datetime.now(UTC).isoformat()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    log_path = str(RUN_DIR / f"{run_id}.log")
    json_path = str(RUN_DIR / f"{run_id}.json")
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=600,
        )
        return_code = proc.returncode
        stdout = (proc.stdout or "")
        stderr = (proc.stderr or "")
        status = "OK" if return_code == 0 else "FAIL"
    except subprocess.TimeoutExpired:
        return_code = -1
        stdout = ""
        stderr = "Command timed out after 600s"
        status = "TIMEOUT"
    except FileNotFoundError:
        return_code = -2
        stdout = ""
        stderr = f"Python interpreter not found: {command[0]}"
        status = "FAIL"
    ended_at = datetime.now(UTC).isoformat()
    result = WebRunResult(
        run_id=run_id,
        action=action,
        status=status,
        return_code=return_code,
        command=command,
        started_at=started_at,
        ended_at=ended_at,
        stdout=stdout,
        stderr=stderr,
        log_path=log_path,
        json_path=json_path,
    )
    # Write run log
    log_lines = [
        f"action: {action}",
        f"command: {" ".join(command)}",
        f"started_at: {started_at}",
        f"ended_at: {ended_at}",
        f"return_code: {return_code}",
        f"status: {status}",
        "",
        "--- stdout ---",
        stdout,
        "",
        "--- stderr ---",
        stderr,
    ]
    Path(log_path).write_text("\n".join(log_lines), encoding="utf-8")
    Path(json_path).write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _action_command(action: str) -> list[str]:
    """Return the shell command for a given action string."""
    python = [sys.executable, "-X", "utf8", "-m", "quant.apps.start"]
    known: dict[str, list[str]] = {
        "daily": python + ["daily"],
        "akshare": python + ["akshare"],
        "doctor": python + ["doctor"],
        "status": python + ["status"],
        "snapshot": python + ["snapshot"],
        "home": python + ["home"],
        "practice-fills": python + ["practice-fills"],
    }
    if action in known:
        return known[action]
    raise ValueError(f"unsupported action: {action}")


def run_action(action: str) -> WebRunResult:
    command = _action_command(action)
    return run_command(action, command)


def run_akshare_backtest(
    start_date: str = "",
    end_date: str = "",
    rebalance: str = "weekly",
    limit: str = "",
) -> WebRunResult:
    python = [sys.executable, "-X", "utf8", "-m", "quant.apps.start", "akshare-backtest"]
    if start_date:
        python.extend(["--start-date", start_date])
    if end_date:
        python.extend(["--end-date", end_date])
    if rebalance:
        python.extend(["--rebalance", rebalance])
    if limit:
        python.extend(["--limit", limit])
    return run_command("akshare-backtest", python)


def import_uploaded_fills(
    filename: str,
    content: bytes,
    skip_refresh: bool = False,
) -> WebRunResult:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / filename
    dest.write_bytes(content)
    python = [sys.executable, "-X", "utf8", "-m", "quant.apps.start", "import-fills"]
    python.extend(["--source", str(dest)])
    if skip_refresh:
        python.append("--skip-refresh")
    return run_command("import-fills", python)


def file_response_path(url_path: str) -> Path:
    """Resolve a /file/... URL path to a local file, restricted to report roots."""
    allowed_roots = [
        ROOT / "research_store/reports",
        ROOT / "research_store/monitoring",
    ]
    # Strip /file/ prefix and decode
    from urllib.parse import unquote
    relative = unquote(url_path.removeprefix("/file/"))
    resolved = (ROOT / relative).resolve()
    # Check it's within an allowed root
    for root in allowed_roots:
        real_root = root.resolve()
        try:
            resolved.relative_to(real_root)
            if resolved.exists():
                return resolved
            raise FileNotFoundError(f"File not found: {resolved}")
        except ValueError:
            continue
    raise PermissionError(f"Path not allowed: {resolved}")


# ---------------------------------------------------------------------------
# stock_picks_html - 选股结果面板
# ---------------------------------------------------------------------------


def stock_picks_html() -> str:
    db = ROOT / "research_store" / "paper_trading.sqlite3"
    mkt_db = ROOT / "research_store" / "market_data.sqlite3"
    if not db.exists():
        return "<p class='empty'>暂无选股数据，请先运行选股流程。</p>"

    # 加载股票名称映射和收盘价
    close_map = {}
    try:
        mc2 = sqlite3.connect(str(mkt_db))
        mc2.row_factory = sqlite3.Row
        cur2 = mc2.execute("SELECT ts_code, close FROM daily_bar WHERE trade_date = (SELECT MAX(trade_date) FROM daily_bar)")
        for row in cur2.fetchall():
            close_map[row[0]] = row[1]
        mc2.close()
    except Exception:
        pass
    name_map = {}
    try:
        mc = sqlite3.connect(str(mkt_db))
        mc.row_factory = sqlite3.Row
        cur = mc.execute("SELECT ts_code, name FROM stocks")
        for row in cur.fetchall():
            name_map[row[0]] = row[1]
        mc.close()
    except Exception:
        pass

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    cu = conn.cursor()

    # 获取最新交易日期
    cu.execute("SELECT MAX(trade_date) FROM signal")
    latest = cu.fetchone()[0]
    cu.execute("SELECT MAX(trade_date) FROM positions")
    pos_latest = cu.fetchone()[0]
    if not pos_latest:
        pos_latest = latest
    # Account overview uses the latest snapshot date, not signal date
    cu.execute("SELECT MAX(trade_date) FROM portfolio_snapshot")
    snap_date = cu.fetchone()[0]
    overview_date = snap_date
    if snap_date:
        pos_latest = snap_date
        pos_latest = snap_date

    # 账户概览
    overview = ""
    if overview_date or latest:
        cu.execute("SELECT * FROM portfolio_snapshot WHERE trade_date=? ORDER BY created_at DESC LIMIT 1", (pos_latest,))
        snap = cu.fetchone()
        if snap:
            cols = [d[0] for d in cu.description]
            snap = dict(zip(cols, snap))
            ta = snap.get("total_asset", 0)
            cash = snap.get("cash", 0)
            mv = snap.get("market_value", 0)
            pr = (snap.get("total_position_ratio") or 0) * 100
            dr = (snap.get("daily_return") or 0) * 100
            cr = (snap.get("cum_return") or 0) * 100
            sdr = "+" if dr is not None and dr >= 0 else ""
            scr = "+" if cr is not None and cr >= 0 else ""
            overview = (
                '<section class="panel"><h2>账户概览 (' + str(overview_date) + ')</h2>'
                '<div class="grid metrics" style="grid-template-columns:repeat(3,minmax(0,1fr))">'
                '<div class="metric"><span>总资产</span><strong>' + f'{ta:,.2f}' + '</strong></div>'
                '<div class="metric"><span>可用现金</span><strong>' + f'{cash:,.2f}' + '</strong></div>'
                '<div class="metric"><span>持仓市值</span><strong>' + f'{mv:,.2f}' + '</strong></div>'
                '<div class="metric"><span>仓位</span><strong>' + f'{pr:.1f}' + '%</strong></div>'
                '<div class="metric"><span>日收益</span><strong>' + sdr + f'{dr:.2f}' + '%</strong></div>'
                '<div class="metric"><span>累计收益</span><strong>' + scr + f'{cr:.2f}' + '%</strong></div>'
                '</div></section>'
            )

        # 选股信号（可能为空）
    signals = []
    if latest:
        cu.execute("SELECT ts_code, strategy_id, signal_type, score, price, reason FROM signal WHERE trade_date=? ORDER BY signal_type ASC, score DESC", (latest,))
        signals = cu.fetchall()
    else:
        latest = overview_date
    positions = cu.fetchall()

    conn.close()

    # 策略名
    strat = signals[0][1] if signals else "N/A"

    sig_rows = ""
    for s in signals[:30]:
        nm = name_map.get(s[0], "-")
        stype = s[2]
        badge = "<span class=\"tag-buy\">买入</span>" if stype == "BUY" else "<span class=\"tag-sell\">卖出</span>"
        price_val = s[4] or close_map.get(s[0], 0)
        sig_rows += f"<tr><td>{badge}</td><td>{s[0]}</td><td>{nm}</td><td>{price_val:.2f}</td><td>{s[3]:.4f}</td><td>{_reason(s[5])}</td></tr>\n"
    if not sig_rows:
        sig_rows = "<tr><td colspan=6>???</td></tr>"
    pos_rows = ""
    for p in positions[:30]:
        nm = name_map.get(p[0], "-")
        w = (p[2] or 0) * 100
        mv2 = p[4] or 0
        pos_rows += f"<tr><td>{p[0]}</td><td>{nm}</td><td>{p[1]}</td><td>{w:.1f}%</td><td>{mv2:.0f}</td></tr>\n"
    if not pos_rows:
        pos_rows = "<tr><td colspan=5>无持仓</td></tr>"

    pos_sec = ""
    if positions:
        pos_sec = f'<section class="panel"><h2>最新持仓 ({pos_latest})</h2><table><thead><tr><th>代码</th><th>名称</th><th>数量</th><th>权重</th><th>占用资金</th></tr></thead><tbody>{pos_rows}</tbody></table></section>'
    sig_sec = f'<section class="panel"><h2>选股信号 ({latest})</h2><p>策略：{strat} | 信号数：{len(signals)} 只</p><table><thead><tr><th>方向</th><th>代码</th><th>名称</th><th>股价</th><th>得分</th><th>理由</th></tr></thead><tbody>{sig_rows}</tbody></table></section>'
    return overview + sig_sec + pos_sec


def _reason(r: str | None) -> str:
    if not r:
        return "-"
    # Try to translate known patterns
    parts = r.split(" by ")
    if len(parts) == 2 and parts[0].startswith("top "):
        rank = parts[0].replace("top ", "")
        return f"动量因子 TOP {rank}"
    return r


# ---------------------------------------------------------------------------
# Reset paper trading
# ---------------------------------------------------------------------------


def reset_paper_trading(initial_cash: float = 1_000_000) -> WebRunResult:
    """Clear all paper trading data and save initial cash to config."""
    import yaml
    config_path = ROOT / "config" / "daily.yaml"
    if config_path.exists():
        try:
            with open(str(config_path), "r", encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
            if "workflow" not in cfg:
                cfg["workflow"] = {}
            cfg["workflow"]["initial_cash"] = initial_cash
            with open(str(config_path), "w", encoding="utf-8") as fh:
                yaml.dump(cfg, fh, default_flow_style=False, allow_unicode=True)
        except Exception:
            pass

    db = ROOT / "research_store" / "paper_trading.sqlite3"
    if not db.exists():
        return WebRunResult(
            run_id="reset", action="reset", status="OK", return_code=0,
            command=[], started_at=datetime.now(UTC).isoformat(),
            ended_at=datetime.now(UTC).isoformat(), stdout="DB not found.", stderr="",
            log_path="", json_path="",
        )

    conn = sqlite3.connect(str(db))
    cu = conn.cursor()
    tables_to_clear = [
        "event_log", "order_fill", "order_intent", "order_risk_check",
        "portfolio_snapshot", "positions", "reconciliation_report", "signal",
        "universe_snapshot", "workflow_lock", "workflow_run",
    ]
    cleared = []
    for t in tables_to_clear:
        cu.execute(f"DELETE FROM {t}")
        cleared.append(f"{t}: {cu.rowcount} rows")
    conn.commit()
    today_str = datetime.now(UTC).strftime("%Y-%m-%d")
    cu.execute(
        "INSERT OR REPLACE INTO portfolio_snapshot (account_id, trade_date, total_asset, cash, market_value, total_position_ratio, daily_return, cum_return, drawdown) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("paper", today_str, initial_cash, initial_cash, 0.0, 0.0, 0.0, 0.0, 0.0)
    )
    conn.commit()
    conn.close()

    log = "\n".join(cleared) + f"\ninitial_snapshot: cash={initial_cash:.0f} at {today_str}"
    return WebRunResult(
        run_id="reset", action="reset", return_code=0, status="OK",
        command=["reset-paper", str(initial_cash)],
        started_at=datetime.now(UTC).isoformat(),
        ended_at=datetime.now(UTC).isoformat(), stdout=log, stderr="",
        log_path="", json_path="",
    )


# ---------------------------------------------------------------------------
# Console HTML renderer
# ---------------------------------------------------------------------------


def render_console_html(message: str = "") -> str:
    """Render the main operator console HTML page."""
    # Load daily summary for status banner
    summary = {}
    summary_path = ROOT / "research_store/reports/daily_summary.json"
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text("utf-8"))
        except Exception:
            pass

    # Load readiness
    readiness = {}
    rpath = ROOT / "research_store/monitoring/readiness.json"
    if rpath.exists():
        try:
            readiness = json.loads(rpath.read_text("utf-8"))
        except Exception:
            pass

    # Load config health
    chealth = {}
    cpath = ROOT / "research_store/monitoring/config_health.json"
    if cpath.exists():
        try:
            chealth = json.loads(cpath.read_text("utf-8"))
        except Exception:
            pass

    # Load execution day-end
    exec_end = {}
    epath = ROOT / "research_store/reports/execution_day_end.json"
    if epath.exists():
        try:
            exec_end = json.loads(epath.read_text("utf-8"))
        except Exception:
            pass

    run_status = summary.get("run_status", "N/A")
    status_class = "ok" if run_status == "SUCCESS" else "warn"
    paper_ready = readiness.get("paper_ready", False)
    ready_class = "ok" if paper_ready else "warn"
    config_status = chealth.get("status", "N/A")
    config_class = "ok" if config_status == "OK" else "warn"
    exec_status = exec_end.get("status", "N/A")
    exec_class = "ok" if exec_status == "READY" else "warn"

    # 选股结果
    picks = stock_picks_html()

    sections = ""

    # 消息提示
    if message:
        sections += f'<div class="message">{html.escape(message)}</div>'

    # 运行状态
    sections += f'''
<section class="panel">
  <h2>系统状态</h2>
  <div class="grid metrics" style="grid-template-columns:repeat(4,minmax(0,1fr))">
    <div class="metric {status_class}"><span>运行状态</span><strong>{run_status}</strong></div>
    <div class="metric {ready_class}"><span>模拟盘</span><strong>{"就绪" if paper_ready else "未就绪"}</strong></div>
    <div class="metric {config_class}"><span>配置</span><strong>{config_status}</strong></div>
    <div class="metric {exec_class}"><span>日终</span><strong>{exec_status}</strong></div>
  </div>
</section>'''

    # 操作按钮
    sections += _action_section()

    # 账户管理
    sections += _account_section()

    # 回测
    sections += _backtest_section()

    # 快速链接
    sections += _links_section()

    # 选股结果
    sections += picks

    # Upload section
    sections += _upload_section()

    head = _head_html()
    return f"""<!doctype html>
<html lang="zh-CN">
{head}
<body>
  <div id="header">
    <h1>本地控制台</h1>
    <span class="subtitle">模拟交易系统</span>
  </div>
  <main>
    {sections}
  </main>
</body>
</html>"""


def _head_html() -> str:
    return f"""<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>量化交易控制台</title>
{_css()}
</head>"""


def _css() -> str:
    return """<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, "Microsoft YaHei", "PingFang SC", sans-serif; background: #f0f2f5; color: #333; line-height: 1.6; }
#header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; padding: 20px 28px; display: flex; align-items: baseline; gap: 16px; }
#header h1 { font-size: 22px; font-weight: 600; }
#header .subtitle { font-size: 13px; opacity: .7; }
main { max-width: 1200px; margin: 20px auto; padding: 0 16px; }
.panel { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.panel h2 { font-size: 16px; font-weight: 600; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #eee; color: #1a1a2e; }
.grid { display: grid; gap: 12px; }
.metrics .metric { background: #f8f9fa; border-radius: 6px; padding: 12px; text-align: center; }
.metrics .metric.ok { border-left: 3px solid #52c41a; }
.metrics .metric.warn { border-left: 3px solid #faad14; }
.metrics .metric.fail { border-left: 3px solid #ff4d4f; }
.metric span { display: block; font-size: 12px; color: #888; }
.metric strong { display: block; font-size: 20px; margin-top: 4px; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; }
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border: none; border-radius: 6px; font-size: 13px; cursor: pointer; text-decoration: none; transition: all .15s; }
.btn-primary { background: #1890ff; color: #fff; }
.btn-primary:hover { background: #096dd9; }
.btn-success { background: #52c41a; color: #fff; }
.btn-success:hover { background: #389e0d; }
.btn-warning { background: #faad14; color: #fff; }
.btn-warning:hover { background: #d48806; }
.btn-danger { background: #ff4d4f; color: #fff; }
.btn-danger:hover { background: #cf1322; }
.btn-outline { background: #fff; color: #333; border: 1px solid #d9d9d9; }
.btn-outline:hover { border-color: #1890ff; color: #1890ff; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.message { background: #e6f7ff; border: 1px solid #91d5ff; border-radius: 6px; padding: 10px 16px; margin-bottom: 16px; font-size: 13px; }
.message.error { background: #fff2f0; border-color: #ffccc7; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #f0f0f0; }
th { background: #fafafa; font-weight: 600; color: #555; }
tr:hover { background: #f5f5f5; }
.empty { color: #999; padding: 24px; text-align: center; }
.tag-buy { display:inline-block; padding:2px 6px; border-radius:3px; font-size:11px; background:#f6ffed; color:#52c41a; border:1px solid #b7eb8f; }
.tag-sell { display:inline-block; padding:2px 6px; border-radius:3px; font-size:11px; background:#fff2f0; color:#ff4d4f; border:1px solid #ffccc7; }
.links { display: flex; flex-wrap: wrap; gap: 8px; }
.links a { padding: 6px 14px; background: #f0f2f5; border-radius: 4px; font-size: 13px; color: #1890ff; text-decoration: none; }
.links a:hover { background: #e6f7ff; }
.form-inline { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.form-inline label { font-size: 13px; color: #555; }
.form-inline input[type=text], .form-inline input[type=number], .form-inline input[type=date] { padding: 6px 10px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 13px; width: 140px; }
.form-inline input[type=text]:focus, .form-inline input[type=date]:focus { outline: none; border-color: #1890ff; }
.form-inline select { padding: 6px 10px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 13px; }
.form-card { background: #f9f9f9; border-radius: 6px; padding: 12px 16px; margin-top: 8px; }
.form-card p { font-size: 12px; color: #888; margin-bottom: 8px; }
</style>"""


def _action_button(label: str, action: str, cls: str = "btn-primary") -> str:
    return f'<form method=POST action="/action/{action}" style="display:inline"><button class="btn {cls}" type=submit>{label}</button></form>'


def _action_section() -> str:
    buttons = (
        _action_button("▶ 运行日常流程", "daily", "btn-primary")
        + _action_button("📡 全市场选股", "akshare", "btn-success")
        + _action_button("🔍 系统体检", "doctor", "btn-outline")
        + _action_button("📸 快照归档", "snapshot", "btn-outline")
        + _action_button("🏠 生成主页", "home", "btn-outline")
    )
    return f"""<section class="panel">
  <h2>刷新执行链路</h2>
  <div class="actions">{buttons}</div>
</section>"""


def _account_section() -> str:
    # read current initial_cash from config
    cash_val = 1000000
    try:
        import yaml
        cp = ROOT / "config" / "daily.yaml"
        with open(str(cp)) as fh:
            cfg = yaml.safe_load(fh) or {}
        cash_val = int(cfg.get("workflow",{}).get("initial_cash",1000000))
    except:
        pass
    return f"""<section class="panel">
  <h2>账户管理</h2>
  <div class="form-card">
    <p>修改初始资金并重置模拟盘（清空所有交易记录）</p>
    <form method=POST action="/reset-paper" class="form-inline">
      <label for="ic">初始资金</label>
      <input type=number id=ic name="initial_cash" value={cash_val} min=10000 step=10000>
      <button class="btn btn-danger" type=submit>重置模拟盘</button>
    </form>
  </div>
</section>"""


def _backtest_section() -> str:
    return f"""<section class="panel">
  <h2>AkShare 全市场回测</h2>
  <div class="form-card">
    <p>设置回测参数，使用 AkShare 获取全市场数据</p>
    <form method=POST action="/akshare-backtest" class="form-inline">
      <label for="sd">开始日期</label>
      <input type=date id=sd name="start_date" value="2025-01-01">
      <label for="ed">结束日期</label>
      <input type=date id=ed name="end_date" value="2026-06-19">
      <label for="rb">再平衡</label>
      <select id=rb name="rebalance"><option value=weekly>周</option><option value=monthly>月</option></select>
      <label for="lim">股票数</label>
      <input type=text id=lim name="limit" value=30 placeholder="默认全市场">
      <button class="btn btn-warning" type=submit>开始回测</button>
    </form>
  </div>
</section>"""


def _links_section() -> str:
    links = [
        "/file/research_store/reports/execution_dashboard.html",
        "/file/research_store/reports/daily_report.html",
        "/file/research_store/reports/execution_day_end.json",
        "/file/research_store/reports/daily_summary.json",
        "/file/research_store/monitoring/readiness.json",
        "/file/research_store/monitoring/config_health.json",
        "/file/research_store/monitoring/metrics.prom",
        "/file/research_store/monitoring/alerts.json",
        "/file/research_store/reports/manual_fill_template.csv",
        "/backtest",
    ]
    names = [
        "执行看板", "日报", "日终报告(JSON)", "运行摘要(JSON)",
        "就绪状态", "配置健康", "监控指标", "告警", "成交模板", "回测可视"
    ]
    items = "".join(f'<a href="{href}">{name}</a>' for href, name in zip(links, names))
    return f"""<section class="panel">
  <h2>快速链接</h2>
  <div class="links">{items}</div>
</section>"""


def _upload_section() -> str:
    return f"""<section class="panel">
  <h2>上传真实成交 CSV</h2>
  <div class="form-card">
    <form method=POST action="/upload-fills" enctype="multipart/form-data" class="form-inline">
      <input type=file name=file accept=".csv">
      <label><input type=checkbox name=skip_refresh value=1> 跳过刷新</label>
      <button class="btn btn-primary" type=submit>上传 CSV</button>
    </form>
  </div>
</section>"""
