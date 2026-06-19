# 从这里开始

这个项目现在有很多底层命令，是为了审计、回放和逐环节排错。日常使用不需要从那些命令开始。

## 1. 最简单启动

在项目根目录运行：

```powershell
python -m quant.apps.start
```

这会跑一个安全的本地纸面演示流程：

1. 生成样例行情和股票池。
2. 清洗样例日线数据。
3. 跑纸面交易日流程。
4. 生成日报。
5. 跑风险守卫。
6. 生成 dry-run 券商提交包。
7. 刷新执行审计和执行看板。

它不会连接券商，不会实盘下单，也不需要 QMT。

## 2. 如果没有 Rust/Cargo

完整演示中的风险守卫是 Rust 实现的。如果本机暂时没有 Rust 环境，先跑纯 Python 日流程：

```powershell
python -m quant.apps.start daily
```

跑完先看：

- `research_store/reports/daily_report.html`
- `research_store/reports/daily_summary.json`
- `research_store/reports/paper_plan.json`

## 3. 查看当前状态

```powershell
python -m quant.apps.start status
```

这个命令会告诉你：

- 日流程是否跑通。
- paper 是否 ready。
- live 是否 ready。
- 执行链路卡在哪里。
- 下一步该做什么。

如果想看更详细的“体检单”，运行：

```powershell
python -m quant.apps.start doctor
```

它会把执行阻塞、执行提醒、QMT 就绪问题、配置问题和最常用文件分开列出来，并写入：

- `research_store/reports/operator_doctor.md`

如果只想快速列出常用文件路径：

```powershell
python -m quant.apps.start paths
```

也可以生成一个本地操作首页：

```powershell
python -m quant.apps.start home
```

然后打开：

- `research_store/reports/operator_home.html`

## 4. 练习手工成交导入

如果你已经跑过完整演示，可以用样例券商成交练习导入：

```powershell
python -m quant.apps.start practice-fills
```

这个命令只会写入样例文件：

- `research_store/sample/manual_fill_template.imported.csv`
- `research_store/reports/manual_fill_import_sample.md`
- `research_store/reports/manual_fill_validation_sample.md`
- `research_store/reports/manual_fill_import_sample_audit.jsonl`

它不会覆盖真实的 `research_store/reports/manual_fill_template.csv`。

## 5. 归档一次运行结果

如果想把当前最新报告留一份快照：

```powershell
python -m quant.apps.start snapshot
```

归档会写到：

- `research_store/archive/<trade_date>_<timestamp>/`

里面会包含关键报告和 `snapshot_manifest.json`，方便以后回看。

同时会生成更适合阅读的：

- `snapshot_manifest.md`
- `snapshot_manifest.html`

## 6. 当前没有 QMT 时怎么理解状态

没有 QMT 接口时，`live_ready=false` 是正常状态。现在应该继续做：

- 样例数据和纸面交易验证。
- dry-run 执行包验证。
- 手工成交导入和对账。
- 执行审计和看板查看。

真正接入 QMT 之前，不需要追求 `live_ready=true`。

## 7. 最常看的文件

- 日报：`research_store/reports/daily_report.html`
- 操作首页：`research_store/reports/operator_home.html`
- 执行看板：`research_store/reports/execution_dashboard.html`
- 就绪状态：`research_store/monitoring/readiness.md`
- 日终执行报告：`research_store/reports/execution_day_end.md`
- 手工下单票据：`research_store/reports/manual_order_ticket.csv`
- 手工成交模板：`research_store/reports/manual_fill_template.csv`

## 8. 真实手工成交流程

当你有券商导出的成交 CSV 后，先导入为系统模板：

```powershell
python -m quant.apps.start import-fills --source path\to\broker_fills.csv
```

它会自动完成：

1. 导入到 `research_store/reports/manual_fill_template.csv`
2. 生成 `research_store/reports/manual_fill_import.md`
3. 生成 `research_store/reports/manual_fill_validation.md`
4. 刷新执行链路和操作首页

不同券商 CSV 的列名可以在这里配置：

- `config/fill_import.yaml`

如果只想导入和校验，不刷新执行链路：

```powershell
python -m quant.apps.start import-fills --source path\to\broker_fills.csv --skip-refresh
```
