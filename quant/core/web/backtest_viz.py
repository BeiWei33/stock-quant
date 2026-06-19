from __future__ import annotations
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


def render_backtest_html() -> str:
    payload = {}
    for key in ["research_store/reports/akshare_backtest.json", "research_store/reports/sample_backtest.json"]:
        fp = ROOT / key
        if fp.exists():
            try:
                payload = json.loads(fp.read_text("utf-8"))
                break
            except Exception:
                pass
    if not payload:
        return _empty_page()
    m = payload.get("metrics", {})
    snapshots = payload.get("snapshots", [])
    rebalances = payload.get("rebalance_records", [])
    equity = payload.get("equity_curve", [])
    bench_eq = payload.get("benchmark_equity_curve", [])
    sid = payload.get("strategy", {}).get("strategy_id", "Momentum")
    return _build_page(sid, payload.get("start_date",""), payload.get("end_date",""),
                       payload.get("benchmark_code","equal_weight"),
                       m, equity, bench_eq, snapshots, rebalances)


def _empty_page() -> str:
    return '<!doctype html><html><body><p>No backtest results.</p><a href="/">返回</a></body></html>'


def _build_page(name, sd, ed, bc, m, equity, bench_eq, snapshots, rebalances):
    def pct(v): return f"{v*100:.2f}%"
    def dec(v): return f"{v:.4f}"

    cards = ""
    for label, key, unit in [("年化收益率","annual_return","%"),("夏普比率","sharpe",""),
        ("最大回撤","max_drawdown","%"),("信息比率","information_ratio","")]:
        v = m.get(key,0)
        cards += f"<div class=\"card\"><span>{label}</span><strong>{pct(v) if unit=='%' else dec(v)}</strong></div>"

    holdings = []
    if snapshots:
        last = snapshots[-1]
        pos = last.get("positions") or last.get("holdings") or []
        if not pos and "weights" in last:
            pos = [{"ts_code":k,"weight":v} for k,v in last["weights"].items()]
        holdings = sorted(pos, key=lambda p: abs(p.get("weight",0)or 0), reverse=True)[:15]
    h_rows = ""
    for h in holdings:
        c = h.get("ts_code","")
        w = (h.get("weight")or 0)*100
        q = h.get("quantity")or h.get("shares")or 0
        a = "u25b2" if w>0 else "u25bc" if w<0 else ""
        h_rows += f"<tr><td>{c}</td><td>{w:.1f}%</td><td>{q}</td><td>{a}</td></tr>"
    if not h_rows: h_rows = "<tr><td colspan=\"4\">无持仓</td></tr>"

    dr = ""
    for label, key, unit in [("年化收益率","annual_return","%"),("基准收益","benchmark_annual_return","%"),
        ("超额收益","excess_return","%"),("夏普比率","sharpe",""),
        ("信息比率","information_ratio",""),("最大回撤","max_drawdown","%"),
        ("波动率","volatility","%"),("贝塔","beta","")]:
        v = m.get(key,0)
        dr += f"<tr><td>{label}</td><td>{pct(v) if unit=='%' else dec(v)}</td></tr>"

    rr = ""
    for r in rebalances[-10:]:
        dt = r.get("trade_date")or r.get("date","")
        n = r.get("trade_count")or r.get("order_count",0)
        rr += f"<tr><td>{dt}</td><td>{n}</td></tr>"
    if not rr: rr = "<tr><td colspan=\"2\">无记录</td></tr>"

    sw, sh, pl, pt = 720, 240, 50, 20
    iw, ih = sw-70, sh-50
    eq_list = [(e.get("trade_date",""),e.get("strategy_equity",0)) for e in equity]
    be_list = [(e.get("trade_date",""),e.get("benchmark_equity",0)) for e in bench_eq]
    all_vals = [v for _,v in eq_list]+[v for _,v in be_list]
    if not all_vals: all_vals = [0,1]
    lo, hi = min(all_vals), max(all_vals)
    if hi==lo: hi=lo+1
    rg, pv = hi-lo, (hi-lo)*0.05 or 1

    def _p(data):
        pts,n = [], max(len(data)-1,1)
        for i,(_,v) in enumerate(data):
            x = pl+(i*iw/n)
            y = pt+ih-((v-lo+pv)/(rg+2*pv)*ih)
            pts.append(("M" if i==0 else "L")+f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    eq_p, be_p = _p(eq_list), _p(be_list)
    yl = "".join(f"<text x='{pl-8}' y='{pt+ih-(pct/100*ih)+4}' text-anchor='end' fill='#667085' font-size='11'>{lo+pv+(rg+2*pv)*pct/100:.0f}</text>" for pct in [0,25,50,75,100])

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>回测结果</title>
<style>
:root {{ color-scheme:light;--ink:#172033;--muted:#667085;--line:#d7deea;--bg:#f5f7fb;--panel:#fff;--accent:#0f766e; }}
* {{ box-sizing:border-box; }}
body {{ margin:0;font-family:Arial,sans-serif;color:var(--ink);background:var(--bg); }}
.shell {{ width:min(1200px,calc(100%-32px));margin:28px auto 48px; }}
h1 {{ margin:0 0 4px;font-size:32px; }}
.grid {{ display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px; }}
.card {{ background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px; }}
.card span {{ display:block;color:var(--muted);font-size:12px;margin-bottom:6px; }}
.card strong {{ font-size:24px; }}
.chart {{ background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px;margin-bottom:20px; }}
.split {{ display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px; }}
table {{ width:100%;border-collapse:collapse; }}
th,td {{ padding:8px 12px;text-align:left;border-bottom:1px solid var(--line);font-size:14px; }}
th {{ color:var(--muted);font-weight:normal;font-size:12px; }}
.back a {{ color:var(--accent);text-decoration:none; }}
@media(max-width:760px){{ .grid,.split{{grid-template-columns:1fr;}} }}
</style></head><body>
<main class="shell">
<div class="back"><a href="/">\u2190 返回</a></div>
<h1>回测结果</h1>
<p>{name} | {sd} ~ {ed} | 基准收益: {bc}</p>
<div class="grid">{cards}</div>
<div class="chart"><h2>净值曲线</h2>
<svg width="{sw}" height="{sh}" viewBox="0 0 {sw} {sh}">
<rect x="{pl}" y="{pt}" width="{iw}" height="{ih}" fill="none" stroke="#d7deea"/>
{yl}
<path d="{eq_p}" fill="none" stroke="#0f766e" stroke-width="2"/>
<path d="{be_p}" fill="none" stroke="#667085" stroke-dasharray="4,3" stroke-width="1.5"/>
</svg></div>
<div class="split">
<div class="card"><h2>指标s</h2><table><tr><th>指标</th><th>数值</th></tr>{dr}</table></div>
<div class="card"><h2>持仓</h2><table><tr><th>代码</th><th>权重</th><th>数量</th><th></th></tr>{h_rows}</table></div>
</div>
<div class="card"><h2>调仓记录</h2><table><tr><th>日期</th><th>订单数</th></tr>{rr}</table></div>
</main></body></html>"""
