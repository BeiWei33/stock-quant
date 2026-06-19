use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::io::Write;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Clone, Debug)]
struct GuardPolicy {
    trade_mode: String,
    max_order_amount: f64,
    max_single_weight: f64,
    max_total_buy_weight: f64,
    max_daily_loss: f64,
    daily_loss: f64,
    trading_start: String,
    trading_end: String,
    now: String,
    reject_duplicate_orders: bool,
}

impl Default for GuardPolicy {
    fn default() -> Self {
        Self {
            trade_mode: "NORMAL".to_string(),
            max_order_amount: 100_000.0,
            max_single_weight: 0.10,
            max_total_buy_weight: 0.95,
            max_daily_loss: 0.05,
            daily_loss: 0.0,
            trading_start: "09:30".to_string(),
            trading_end: "15:00".to_string(),
            now: "14:30".to_string(),
            reject_duplicate_orders: true,
        }
    }
}

#[derive(Debug)]
struct CliArgs {
    orders: PathBuf,
    output: Option<PathBuf>,
    output_md: Option<PathBuf>,
    audit_log: Option<PathBuf>,
    control_file: Option<PathBuf>,
    policy: GuardPolicy,
}

#[derive(Clone, Debug)]
struct OrderIntent {
    order_id: String,
    account_id: String,
    strategy_id: String,
    ts_code: String,
    side: String,
    quantity: i64,
    price: f64,
    target_weight: f64,
    trade_date: String,
}

#[derive(Clone, Debug)]
struct Rejection {
    order_id: String,
    account_id: String,
    strategy_id: String,
    ts_code: String,
    side: String,
    trade_date: String,
    rule: String,
    reason: String,
}

#[derive(Debug)]
struct GuardReport {
    allowed: bool,
    input_orders: usize,
    accepted_orders: usize,
    rejected_orders: usize,
    total_buy_weight: f64,
    control_file: String,
    policy: GuardPolicy,
    rule_counts: BTreeMap<String, usize>,
    rejections: Vec<Rejection>,
}

impl GuardReport {
    fn to_json(&self) -> String {
        let rule_counts = self
            .rule_counts
            .iter()
            .map(|(rule, count)| format!("    \"{}\": {}", json_escape(rule), count))
            .collect::<Vec<_>>()
            .join(",\n");
        let rejections = self
            .rejections
            .iter()
            .map(|rejection| {
                format!(
                    concat!(
                        "{{",
                        "\"order_id\":\"{}\",",
                        "\"account_id\":\"{}\",",
                        "\"strategy_id\":\"{}\",",
                        "\"ts_code\":\"{}\",",
                        "\"side\":\"{}\",",
                        "\"trade_date\":\"{}\",",
                        "\"rule\":\"{}\",",
                        "\"reason\":\"{}\"",
                        "}}"
                    ),
                    json_escape(&rejection.order_id),
                    json_escape(&rejection.account_id),
                    json_escape(&rejection.strategy_id),
                    json_escape(&rejection.ts_code),
                    json_escape(&rejection.side),
                    json_escape(&rejection.trade_date),
                    json_escape(&rejection.rule),
                    json_escape(&rejection.reason)
                )
            })
            .collect::<Vec<_>>()
            .join(",\n    ");
        format!(
            concat!(
                "{{\n",
                "  \"allowed\": {},\n",
                "  \"input_orders\": {},\n",
                "  \"accepted_orders\": {},\n",
                "  \"rejected_orders\": {},\n",
                "  \"total_buy_weight\": {},\n",
                "  \"control_file\": \"{}\",\n",
                "  \"policy\": {{\n",
                "    \"trade_mode\": \"{}\",\n",
                "    \"max_order_amount\": {},\n",
                "    \"max_single_weight\": {},\n",
                "    \"max_total_buy_weight\": {},\n",
                "    \"max_daily_loss\": {},\n",
                "    \"daily_loss\": {},\n",
                "    \"trading_start\": \"{}\",\n",
                "    \"trading_end\": \"{}\",\n",
                "    \"now\": \"{}\",\n",
                "    \"reject_duplicate_orders\": {}\n",
                "  }},\n",
                "  \"rule_counts\": {{\n{}\n  }},\n",
                "  \"rejections\": [\n    {}\n  ]\n",
                "}}\n"
            ),
            self.allowed,
            self.input_orders,
            self.accepted_orders,
            self.rejected_orders,
            self.total_buy_weight,
            json_escape(&self.control_file),
            json_escape(&self.policy.trade_mode),
            self.policy.max_order_amount,
            self.policy.max_single_weight,
            self.policy.max_total_buy_weight,
            self.policy.max_daily_loss,
            self.policy.daily_loss,
            json_escape(&self.policy.trading_start),
            json_escape(&self.policy.trading_end),
            json_escape(&self.policy.now),
            self.policy.reject_duplicate_orders,
            rule_counts,
            rejections
        )
    }

    fn to_audit_json_line(&self, epoch_seconds: u64, orders_path: &str) -> String {
        let rule_counts = self
            .rule_counts
            .iter()
            .map(|(rule, count)| format!("\"{}\":{}", json_escape(rule), count))
            .collect::<Vec<_>>()
            .join(",");
        let rejections = self
            .rejections
            .iter()
            .map(|rejection| {
                format!(
                    concat!(
                        "{{",
                        "\"order_id\":\"{}\",",
                        "\"account_id\":\"{}\",",
                        "\"strategy_id\":\"{}\",",
                        "\"ts_code\":\"{}\",",
                        "\"side\":\"{}\",",
                        "\"trade_date\":\"{}\",",
                        "\"rule\":\"{}\",",
                        "\"reason\":\"{}\"",
                        "}}"
                    ),
                    json_escape(&rejection.order_id),
                    json_escape(&rejection.account_id),
                    json_escape(&rejection.strategy_id),
                    json_escape(&rejection.ts_code),
                    json_escape(&rejection.side),
                    json_escape(&rejection.trade_date),
                    json_escape(&rejection.rule),
                    json_escape(&rejection.reason)
                )
            })
            .collect::<Vec<_>>()
            .join(",");
        format!(
            concat!(
                "{{",
                "\"event_type\":\"RiskGuardRun\",",
                "\"epoch_seconds\":{},",
                "\"orders_path\":\"{}\",",
                "\"control_file\":\"{}\",",
                "\"allowed\":{},",
                "\"input_orders\":{},",
                "\"accepted_orders\":{},",
                "\"rejected_orders\":{},",
                "\"total_buy_weight\":{},",
                "\"rule_counts\":{{{}}},",
                "\"rejections\":[{}]",
                "}}\n"
            ),
            epoch_seconds,
            json_escape(orders_path),
            json_escape(&self.control_file),
            self.allowed,
            self.input_orders,
            self.accepted_orders,
            self.rejected_orders,
            self.total_buy_weight,
            rule_counts,
            rejections
        )
    }

    fn to_markdown(&self) -> String {
        let mut lines = vec![
            "# Rust Risk Guard Report".to_string(),
            "".to_string(),
            "## Summary".to_string(),
            "| Metric | Value |".to_string(),
            "| --- | --- |".to_string(),
            format!("| Allowed | {} |", self.allowed),
            format!("| Input Orders | {} |", self.input_orders),
            format!("| Accepted Orders | {} |", self.accepted_orders),
            format!("| Rejected Orders | {} |", self.rejected_orders),
            format!("| Total Buy Weight | {:.4} |", self.total_buy_weight),
            format!("| Control File | {} |", self.control_file),
            "".to_string(),
            "## Policy".to_string(),
            "| Rule | Value |".to_string(),
            "| --- | --- |".to_string(),
            format!("| Trade Mode | {} |", self.policy.trade_mode),
            format!("| Max Order Amount | {:.2} |", self.policy.max_order_amount),
            format!(
                "| Max Single Weight | {:.4} |",
                self.policy.max_single_weight
            ),
            format!(
                "| Max Total Buy Weight | {:.4} |",
                self.policy.max_total_buy_weight
            ),
            format!("| Max Daily Loss | {:.4} |", self.policy.max_daily_loss),
            format!("| Daily Loss | {:.4} |", self.policy.daily_loss),
            format!(
                "| Trading Window | {}-{} |",
                self.policy.trading_start, self.policy.trading_end
            ),
            format!("| Now | {} |", self.policy.now),
            "".to_string(),
            "## Rejections".to_string(),
        ];
        if self.rejections.is_empty() {
            lines.push("_No rejected orders._".to_string());
        } else {
            lines.push("| Order | Code | Side | Rule | Reason |".to_string());
            lines.push("| --- | --- | --- | --- | --- |".to_string());
            for rejection in &self.rejections {
                lines.push(format!(
                    "| {} | {} | {} | {} | {} |",
                    md_escape(&rejection.order_id),
                    md_escape(&rejection.ts_code),
                    md_escape(&rejection.side),
                    md_escape(&rejection.rule),
                    md_escape(&rejection.reason)
                ));
            }
        }
        lines.push(String::new());
        lines.join("\n")
    }
}

fn main() {
    match run() {
        Ok(report) if report.allowed => {}
        Ok(_) => std::process::exit(2),
        Err(err) => {
            eprintln!("risk_guard error: {err}");
            std::process::exit(1);
        }
    }
}

fn run() -> Result<GuardReport, Box<dyn std::error::Error>> {
    let args = parse_args(env::args().skip(1).collect())?;
    let content = fs::read_to_string(&args.orders)?;
    let orders = parse_orders_csv(&content)?;
    let mut report = validate_orders(&orders, &args.policy);
    report.control_file = args
        .control_file
        .as_ref()
        .map(|path| path.display().to_string())
        .unwrap_or_default();
    if let Some(output) = &args.output {
        write_text(output, &report.to_json())?;
    }
    if let Some(output_md) = &args.output_md {
        write_text(output_md, &report.to_markdown())?;
    }
    if let Some(audit_log) = &args.audit_log {
        append_text(
            audit_log,
            &report.to_audit_json_line(current_epoch_seconds(), &args.orders.display().to_string()),
        )?;
    }
    println!(
        "allowed={}, input_orders={}, accepted_orders={}, rejected_orders={}",
        report.allowed, report.input_orders, report.accepted_orders, report.rejected_orders
    );
    if let Some(output) = &args.output {
        println!("Wrote risk guard report to {}", output.display());
    }
    if let Some(output_md) = &args.output_md {
        println!("Wrote risk guard Markdown to {}", output_md.display());
    }
    if let Some(audit_log) = &args.audit_log {
        println!("Appended risk guard audit log to {}", audit_log.display());
    }
    Ok(report)
}

fn parse_args(args: Vec<String>) -> Result<CliArgs, Box<dyn std::error::Error>> {
    let mut orders = None;
    let mut output = None;
    let mut output_md = None;
    let mut audit_log = None;
    let mut control_file = None;
    let mut policy = GuardPolicy::default();
    let mut index = 0;
    while index < args.len() {
        match args[index].as_str() {
            "--orders" => orders = Some(PathBuf::from(take_value(&args, &mut index)?)),
            "--output" => output = Some(PathBuf::from(take_value(&args, &mut index)?)),
            "--output-md" => output_md = Some(PathBuf::from(take_value(&args, &mut index)?)),
            "--audit-log" => audit_log = Some(PathBuf::from(take_value(&args, &mut index)?)),
            "--control-file" => {
                control_file = Some(PathBuf::from(take_value(&args, &mut index)?));
                policy = load_control_file(control_file.as_ref().expect("control file path"))?;
            }
            "--trade-mode" => {
                policy.trade_mode = normalize_trade_mode(&take_value(&args, &mut index)?)?
            }
            "--max-order-amount" => {
                policy.max_order_amount = take_value(&args, &mut index)?.parse::<f64>()?
            }
            "--max-single-weight" => {
                policy.max_single_weight = take_value(&args, &mut index)?.parse::<f64>()?
            }
            "--max-total-buy-weight" => {
                policy.max_total_buy_weight = take_value(&args, &mut index)?.parse::<f64>()?
            }
            "--max-daily-loss" => {
                policy.max_daily_loss = take_value(&args, &mut index)?.parse::<f64>()?
            }
            "--daily-loss" => policy.daily_loss = take_value(&args, &mut index)?.parse::<f64>()?,
            "--trading-start" => policy.trading_start = take_value(&args, &mut index)?,
            "--trading-end" => policy.trading_end = take_value(&args, &mut index)?,
            "--now" => policy.now = take_value(&args, &mut index)?,
            "--allow-duplicate-orders" => policy.reject_duplicate_orders = false,
            "--help" | "-h" => return Err(usage().into()),
            value => return Err(format!("unknown argument: {value}\n{}", usage()).into()),
        }
        index += 1;
    }
    Ok(CliArgs {
        orders: orders.ok_or_else(usage)?,
        output,
        output_md,
        audit_log,
        control_file,
        policy,
    })
}

fn usage() -> String {
    concat!(
        "usage: risk_guard --orders orders.csv [--output report.json] [--output-md report.md] ",
        "[--audit-log audit.jsonl] ",
        "[--control-file risk_guard_control.env] ",
        "[--trade-mode normal|sell_only|halt] ",
        "[--max-order-amount 100000] [--max-single-weight 0.10] ",
        "[--max-total-buy-weight 0.95] [--daily-loss 0.0] [--max-daily-loss 0.05] [--now 14:30]"
    )
    .to_string()
}

fn take_value(args: &[String], index: &mut usize) -> Result<String, Box<dyn std::error::Error>> {
    *index += 1;
    args.get(*index)
        .cloned()
        .ok_or_else(|| "missing argument value".into())
}

fn normalize_trade_mode(value: &str) -> Result<String, Box<dyn std::error::Error>> {
    let normalized = value.trim().to_ascii_uppercase().replace('-', "_");
    match normalized.as_str() {
        "NORMAL" | "SELL_ONLY" | "HALT" => Ok(normalized),
        _ => Err(format!("unsupported trade mode: {value}").into()),
    }
}

fn load_control_file(path: &PathBuf) -> Result<GuardPolicy, Box<dyn std::error::Error>> {
    let content = fs::read_to_string(path)?;
    let mut policy = GuardPolicy::default();
    for raw_line in content.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let Some((raw_key, raw_value)) = line.split_once('=').or_else(|| line.split_once(':'))
        else {
            continue;
        };
        let key = raw_key.trim().to_ascii_lowercase().replace('-', "_");
        let value = raw_value.trim().trim_matches('"').trim_matches('\'');
        match key.as_str() {
            "trade_mode" => policy.trade_mode = normalize_trade_mode(value)?,
            "max_order_amount" => policy.max_order_amount = value.parse::<f64>()?,
            "max_single_weight" => policy.max_single_weight = value.parse::<f64>()?,
            "max_total_buy_weight" => policy.max_total_buy_weight = value.parse::<f64>()?,
            "max_daily_loss" => policy.max_daily_loss = value.parse::<f64>()?,
            "daily_loss" => policy.daily_loss = value.parse::<f64>()?,
            "trading_start" => policy.trading_start = value.to_string(),
            "trading_end" => policy.trading_end = value.to_string(),
            "now" => policy.now = value.to_string(),
            "reject_duplicate_orders" => policy.reject_duplicate_orders = parse_bool(value),
            _ => {}
        }
    }
    Ok(policy)
}

fn parse_bool(value: &str) -> bool {
    matches!(
        value.trim().to_ascii_lowercase().as_str(),
        "true" | "1" | "yes" | "on"
    )
}

fn parse_orders_csv(content: &str) -> Result<Vec<OrderIntent>, Box<dyn std::error::Error>> {
    let mut lines = content.lines();
    let header = lines.next().ok_or("empty orders csv")?;
    let headers = split_csv_line(header);
    let index = OrderColumns::from_headers(&headers)?;
    let mut orders = Vec::new();
    for raw_line in lines {
        if raw_line.trim().is_empty() {
            continue;
        }
        let cols = split_csv_line(raw_line);
        orders.push(OrderIntent {
            order_id: get_col(&cols, index.order_id).to_string(),
            account_id: get_col(&cols, index.account_id).to_string(),
            strategy_id: get_col(&cols, index.strategy_id).to_string(),
            ts_code: get_col(&cols, index.ts_code).to_string(),
            side: get_col(&cols, index.side).to_ascii_uppercase(),
            quantity: get_col(&cols, index.quantity).parse::<i64>()?,
            price: get_col(&cols, index.price).parse::<f64>()?,
            target_weight: get_col(&cols, index.target_weight).parse::<f64>()?,
            trade_date: get_col(&cols, index.trade_date).to_string(),
        });
    }
    Ok(orders)
}

#[derive(Debug)]
struct OrderColumns {
    order_id: usize,
    account_id: usize,
    strategy_id: usize,
    ts_code: usize,
    side: usize,
    quantity: usize,
    price: usize,
    target_weight: usize,
    trade_date: usize,
}

impl OrderColumns {
    fn from_headers(headers: &[String]) -> Result<Self, Box<dyn std::error::Error>> {
        Ok(Self {
            order_id: find_column(headers, "order_id")?,
            account_id: find_column(headers, "account_id")?,
            strategy_id: find_column(headers, "strategy_id")?,
            ts_code: find_column(headers, "ts_code")?,
            side: find_column(headers, "side")?,
            quantity: find_column(headers, "quantity")?,
            price: find_column(headers, "price")?,
            target_weight: find_column(headers, "target_weight")?,
            trade_date: find_column(headers, "trade_date")?,
        })
    }
}

fn validate_orders(orders: &[OrderIntent], policy: &GuardPolicy) -> GuardReport {
    let mut rejections = Vec::new();
    let mut rule_counts: BTreeMap<String, usize> = BTreeMap::new();
    let mut seen_order_ids = BTreeSet::new();
    let trade_mode = policy.trade_mode.to_ascii_uppercase();
    let in_trading_window =
        is_in_trading_window(&policy.now, &policy.trading_start, &policy.trading_end);
    let total_buy_weight = orders
        .iter()
        .filter(|order| order.side == "BUY")
        .map(|order| order.target_weight.max(0.0))
        .sum::<f64>();

    if total_buy_weight > policy.max_total_buy_weight + 1e-12 {
        for order in orders.iter().filter(|order| order.side == "BUY") {
            push_rejection(
                &mut rejections,
                &mut rule_counts,
                order,
                "max_total_buy_weight",
                format!(
                    "total buy target weight {:.4} exceeds limit {:.4}",
                    total_buy_weight, policy.max_total_buy_weight
                ),
            );
        }
    }

    for order in orders {
        let amount = order.quantity as f64 * order.price;
        if trade_mode == "HALT" {
            push_rejection(
                &mut rejections,
                &mut rule_counts,
                order,
                "trade_mode_halt",
                "trade mode HALT rejects every order".to_string(),
            );
        }
        if order.side == "BUY" && trade_mode == "SELL_ONLY" {
            push_rejection(
                &mut rejections,
                &mut rule_counts,
                order,
                "trade_mode_sell_only",
                "trade mode SELL_ONLY rejects buy orders".to_string(),
            );
        }
        if order.side == "BUY" && policy.daily_loss >= policy.max_daily_loss {
            push_rejection(
                &mut rejections,
                &mut rule_counts,
                order,
                "daily_loss_lock",
                format!(
                    "daily loss {:.4} reached limit {:.4}; buy orders are locked",
                    policy.daily_loss, policy.max_daily_loss
                ),
            );
        }
        if order.quantity <= 0 || order.price <= 0.0 {
            push_rejection(
                &mut rejections,
                &mut rule_counts,
                order,
                "invalid_order",
                "quantity and price must be positive".to_string(),
            );
        }
        if policy.reject_duplicate_orders && !seen_order_ids.insert(order.order_id.clone()) {
            push_rejection(
                &mut rejections,
                &mut rule_counts,
                order,
                "duplicate_order",
                "duplicate order_id".to_string(),
            );
        }
        if order.side == "BUY" && !in_trading_window {
            push_rejection(
                &mut rejections,
                &mut rule_counts,
                order,
                "trading_window",
                format!(
                    "buy order outside trading window {}-{} at {}",
                    policy.trading_start, policy.trading_end, policy.now
                ),
            );
        }
        if amount > policy.max_order_amount + 1e-12 {
            push_rejection(
                &mut rejections,
                &mut rule_counts,
                order,
                "max_order_amount",
                format!(
                    "order amount {:.2} exceeds limit {:.2}",
                    amount, policy.max_order_amount
                ),
            );
        }
        if order.target_weight > policy.max_single_weight + 1e-12 {
            push_rejection(
                &mut rejections,
                &mut rule_counts,
                order,
                "max_single_weight",
                format!(
                    "target weight {:.4} exceeds limit {:.4}",
                    order.target_weight, policy.max_single_weight
                ),
            );
        }
    }

    let rejected_order_ids = rejections
        .iter()
        .map(|rejection| rejection.order_id.clone())
        .collect::<BTreeSet<_>>();
    let rejected_orders = rejected_order_ids.len();
    let accepted_orders = orders.len().saturating_sub(rejected_orders);
    GuardReport {
        allowed: rejected_orders == 0,
        input_orders: orders.len(),
        accepted_orders,
        rejected_orders,
        total_buy_weight,
        policy: policy.clone(),
        control_file: String::new(),
        rule_counts,
        rejections,
    }
}

fn push_rejection(
    rejections: &mut Vec<Rejection>,
    rule_counts: &mut BTreeMap<String, usize>,
    order: &OrderIntent,
    rule: &str,
    reason: String,
) {
    *rule_counts.entry(rule.to_string()).or_insert(0) += 1;
    rejections.push(Rejection {
        order_id: order.order_id.clone(),
        account_id: order.account_id.clone(),
        strategy_id: order.strategy_id.clone(),
        ts_code: order.ts_code.clone(),
        side: order.side.clone(),
        trade_date: order.trade_date.clone(),
        rule: rule.to_string(),
        reason,
    });
}

fn is_in_trading_window(now: &str, start: &str, end: &str) -> bool {
    match (parse_hhmm(now), parse_hhmm(start), parse_hhmm(end)) {
        (Some(now), Some(start), Some(end)) => now >= start && now <= end,
        _ => false,
    }
}

fn parse_hhmm(value: &str) -> Option<i32> {
    let (hour, minute) = value.split_once(':')?;
    let hour = hour.parse::<i32>().ok()?;
    let minute = minute.parse::<i32>().ok()?;
    Some(hour * 60 + minute)
}

fn split_csv_line(line: &str) -> Vec<String> {
    line.split(',')
        .map(|part| part.trim().to_string())
        .collect()
}

fn find_column(headers: &[String], name: &str) -> Result<usize, Box<dyn std::error::Error>> {
    headers
        .iter()
        .position(|header| header == name)
        .ok_or_else(|| format!("orders csv missing column: {name}").into())
}

fn get_col(cols: &[String], index: usize) -> &str {
    cols.get(index).map(|value| value.as_str()).unwrap_or("")
}

fn write_text(path: &PathBuf, content: &str) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut file = fs::File::create(path)?;
    file.write_all(content.as_bytes())?;
    Ok(())
}

fn append_text(path: &PathBuf, content: &str) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?;
    file.write_all(content.as_bytes())?;
    Ok(())
}

fn current_epoch_seconds() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0)
}

fn json_escape(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
}

fn md_escape(value: &str) -> String {
    value.replace('|', "\\|").replace('\n', " ")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn order(
        order_id: &str,
        side: &str,
        quantity: i64,
        price: f64,
        target_weight: f64,
    ) -> OrderIntent {
        OrderIntent {
            order_id: order_id.to_string(),
            account_id: "paper".to_string(),
            strategy_id: "momentum_rank".to_string(),
            ts_code: "000001.SZ".to_string(),
            side: side.to_string(),
            quantity,
            price,
            target_weight,
            trade_date: "2024-09-09".to_string(),
        }
    }

    #[test]
    fn accepts_orders_inside_hard_limits() {
        let orders = vec![order("o1", "BUY", 100, 10.0, 0.05)];
        let report = validate_orders(&orders, &GuardPolicy::default());

        assert!(report.allowed);
        assert_eq!(report.accepted_orders, 1);
        assert_eq!(report.rejected_orders, 0);
    }

    #[test]
    fn rejects_large_amount_and_single_weight() {
        let orders = vec![order("o1", "BUY", 20_000, 10.0, 0.20)];
        let report = validate_orders(&orders, &GuardPolicy::default());

        assert!(!report.allowed);
        assert_eq!(report.rejected_orders, 1);
        assert_eq!(report.rule_counts.get("max_order_amount"), Some(&1));
        assert_eq!(report.rule_counts.get("max_single_weight"), Some(&1));
    }

    #[test]
    fn rejects_duplicates_and_outside_trading_window() {
        let policy = GuardPolicy {
            now: "20:00".to_string(),
            ..GuardPolicy::default()
        };
        let orders = vec![
            order("o1", "BUY", 100, 10.0, 0.05),
            order("o1", "BUY", 100, 10.0, 0.05),
        ];
        let report = validate_orders(&orders, &policy);

        assert!(!report.allowed);
        assert_eq!(report.rejected_orders, 1);
        assert_eq!(report.rule_counts.get("duplicate_order"), Some(&1));
        assert_eq!(report.rule_counts.get("trading_window"), Some(&2));
    }

    #[test]
    fn halt_mode_rejects_every_order() {
        let policy = GuardPolicy {
            trade_mode: "HALT".to_string(),
            ..GuardPolicy::default()
        };
        let orders = vec![
            order("o1", "BUY", 100, 10.0, 0.05),
            order("o2", "SELL", 100, 10.0, 0.0),
        ];
        let report = validate_orders(&orders, &policy);

        assert!(!report.allowed);
        assert_eq!(report.rejected_orders, 2);
        assert_eq!(report.rule_counts.get("trade_mode_halt"), Some(&2));
    }

    #[test]
    fn sell_only_mode_rejects_buys_but_allows_sells() {
        let policy = GuardPolicy {
            trade_mode: "SELL_ONLY".to_string(),
            ..GuardPolicy::default()
        };
        let orders = vec![
            order("o1", "BUY", 100, 10.0, 0.05),
            order("o2", "SELL", 100, 10.0, 0.0),
        ];
        let report = validate_orders(&orders, &policy);

        assert!(!report.allowed);
        assert_eq!(report.accepted_orders, 1);
        assert_eq!(report.rejected_orders, 1);
        assert_eq!(report.rule_counts.get("trade_mode_sell_only"), Some(&1));
    }

    #[test]
    fn daily_loss_lock_rejects_buys() {
        let policy = GuardPolicy {
            daily_loss: 0.05,
            max_daily_loss: 0.05,
            ..GuardPolicy::default()
        };
        let orders = vec![
            order("o1", "BUY", 100, 10.0, 0.05),
            order("o2", "SELL", 100, 10.0, 0.0),
        ];
        let report = validate_orders(&orders, &policy);

        assert!(!report.allowed);
        assert_eq!(report.accepted_orders, 1);
        assert_eq!(report.rejected_orders, 1);
        assert_eq!(report.rule_counts.get("daily_loss_lock"), Some(&1));
    }

    #[test]
    fn parses_orders_csv() {
        let input = concat!(
            "order_id,account_id,strategy_id,ts_code,side,quantity,price,target_weight,trade_date\n",
            "o1,paper,momentum_rank,000001.SZ,BUY,100,10.5,0.05,2024-09-09\n"
        );
        let orders = parse_orders_csv(input).unwrap();

        assert_eq!(orders.len(), 1);
        assert_eq!(orders[0].order_id, "o1");
        assert_eq!(orders[0].quantity, 100);
        assert_eq!(orders[0].price, 10.5);
    }

    #[test]
    fn normalizes_trade_mode() {
        assert_eq!(normalize_trade_mode("sell-only").unwrap(), "SELL_ONLY");
        assert!(normalize_trade_mode("unknown").is_err());
    }

    #[test]
    fn loads_control_file() {
        let path = std::env::temp_dir().join("risk_guard_control_test.env");
        fs::write(
            &path,
            concat!(
                "trade_mode=sell-only\n",
                "max_order_amount=50000\n",
                "max_single_weight=0.08\n",
                "max_total_buy_weight=0.50\n",
                "daily_loss=0.03\n",
                "max_daily_loss=0.05\n",
                "trading_start=09:45\n",
                "trading_end=14:55\n",
                "now=10:00\n",
                "reject_duplicate_orders=false\n",
            ),
        )
        .unwrap();

        let policy = load_control_file(&path).unwrap();

        assert_eq!(policy.trade_mode, "SELL_ONLY");
        assert_eq!(policy.max_order_amount, 50_000.0);
        assert_eq!(policy.max_single_weight, 0.08);
        assert_eq!(policy.max_total_buy_weight, 0.50);
        assert_eq!(policy.daily_loss, 0.03);
        assert_eq!(policy.max_daily_loss, 0.05);
        assert_eq!(policy.trading_start, "09:45");
        assert_eq!(policy.trading_end, "14:55");
        assert!(!policy.reject_duplicate_orders);

        let _ = fs::remove_file(path);
    }

    #[test]
    fn audit_json_line_contains_run_summary() {
        let orders = vec![order("o1", "BUY", 100, 10.0, 0.05)];
        let report = validate_orders(&orders, &GuardPolicy::default());
        let line = report.to_audit_json_line(1_700_000_000, "orders.csv");

        assert!(line.contains("\"event_type\":\"RiskGuardRun\""));
        assert!(line.contains("\"orders_path\":\"orders.csv\""));
        assert!(line.contains("\"allowed\":true"));
        assert!(line.ends_with('\n'));
    }
}
