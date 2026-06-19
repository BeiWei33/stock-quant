use std::env;
use std::fs;
use std::io::{self, Write};
use std::path::PathBuf;

#[derive(Clone, Debug, Eq, PartialEq)]
struct CleaningPolicy {
    fix_ohlc_envelope: bool,
    flag_zero_volume: bool,
    flag_non_positive_price: bool,
    flag_non_positive_amount: bool,
    diff_sample_limit: usize,
}

impl Default for CleaningPolicy {
    fn default() -> Self {
        Self {
            fix_ohlc_envelope: true,
            flag_zero_volume: true,
            flag_non_positive_price: true,
            flag_non_positive_amount: false,
            diff_sample_limit: 20,
        }
    }
}

#[derive(Debug)]
struct CliArgs {
    input: PathBuf,
    output: PathBuf,
    report: Option<PathBuf>,
    report_md: Option<PathBuf>,
    config: Option<PathBuf>,
    no_fix_ohlc_envelope: bool,
    no_flag_zero_volume: bool,
    no_flag_non_positive_price: bool,
    flag_non_positive_amount: bool,
    diff_sample_limit: Option<usize>,
}

#[derive(Debug)]
struct ColumnIndex {
    ts_code: Option<usize>,
    trade_date: Option<usize>,
    open: Option<usize>,
    high: Option<usize>,
    low: Option<usize>,
    close: Option<usize>,
    volume: Option<usize>,
    amount: Option<usize>,
    quality_flag: Option<usize>,
}

#[derive(Clone, Debug)]
struct CleaningDiff {
    ts_code: String,
    trade_date: String,
    field: String,
    before: String,
    after: String,
    rule: String,
    action: String,
}

#[derive(Debug)]
struct CleaningReport {
    input_rows: usize,
    output_rows: usize,
    changed_row_count: usize,
    high_fixed_count: usize,
    low_fixed_count: usize,
    non_positive_volume_count: usize,
    non_positive_amount_count: usize,
    auto_fixed_row_count: usize,
    manual_review_row_count: usize,
    zero_volume_count: usize,
    non_positive_price_count: usize,
    non_positive_amount_flagged_count: usize,
    policy: CleaningPolicy,
    diffs: Vec<CleaningDiff>,
}

impl CleaningReport {
    fn to_json(&self) -> String {
        let diffs = self
            .diffs
            .iter()
            .map(|diff| {
                format!(
                    concat!(
                        "{{",
                        "\"ts_code\":\"{}\",",
                        "\"trade_date\":\"{}\",",
                        "\"field\":\"{}\",",
                        "\"before\":\"{}\",",
                        "\"after\":\"{}\",",
                        "\"rule\":\"{}\",",
                        "\"action\":\"{}\"",
                        "}}"
                    ),
                    json_escape(&diff.ts_code),
                    json_escape(&diff.trade_date),
                    json_escape(&diff.field),
                    json_escape(&diff.before),
                    json_escape(&diff.after),
                    json_escape(&diff.rule),
                    json_escape(&diff.action)
                )
            })
            .collect::<Vec<_>>()
            .join(",\n    ");
        format!(
            concat!(
                "{{\n",
                "  \"input_rows\": {},\n",
                "  \"output_rows\": {},\n",
                "  \"changed_row_count\": {},\n",
                "  \"high_fixed_count\": {},\n",
                "  \"low_fixed_count\": {},\n",
                "  \"non_positive_volume_count\": {},\n",
                "  \"non_positive_amount_count\": {},\n",
                "  \"auto_fixed_row_count\": {},\n",
                "  \"manual_review_row_count\": {},\n",
                "  \"rule_counts\": {{\n",
                "    \"ohlc_envelope_high\": {},\n",
                "    \"ohlc_envelope_low\": {},\n",
                "    \"zero_volume\": {},\n",
                "    \"non_positive_price\": {},\n",
                "    \"non_positive_amount\": {}\n",
                "  }},\n",
                "  \"policy\": {{\n",
                "    \"fix_ohlc_envelope\": {},\n",
                "    \"flag_zero_volume\": {},\n",
                "    \"flag_non_positive_price\": {},\n",
                "    \"flag_non_positive_amount\": {},\n",
                "    \"diff_sample_limit\": {}\n",
                "  }},\n",
                "  \"diffs\": [\n    {}\n  ],\n",
                "  \"changed_rows\": {}\n",
                "}}\n"
            ),
            self.input_rows,
            self.output_rows,
            self.changed_row_count,
            self.high_fixed_count,
            self.low_fixed_count,
            self.non_positive_volume_count,
            self.non_positive_amount_count,
            self.auto_fixed_row_count,
            self.manual_review_row_count,
            self.high_fixed_count,
            self.low_fixed_count,
            self.zero_volume_count,
            self.non_positive_price_count,
            self.non_positive_amount_flagged_count,
            self.policy.fix_ohlc_envelope,
            self.policy.flag_zero_volume,
            self.policy.flag_non_positive_price,
            self.policy.flag_non_positive_amount,
            self.policy.diff_sample_limit,
            diffs,
            self.changed_row_count
        )
    }

    fn to_markdown(&self) -> String {
        let mut lines = vec![
            "# Data Cleaning Report".to_string(),
            "".to_string(),
            "## Summary".to_string(),
            "| Metric | Value |".to_string(),
            "| --- | --- |".to_string(),
            format!("| Input Rows | {} |", self.input_rows),
            format!("| Output Rows | {} |", self.output_rows),
            format!("| Changed Rows | {} |", self.changed_row_count),
            format!("| Auto Fixed Rows | {} |", self.auto_fixed_row_count),
            format!("| Manual Review Rows | {} |", self.manual_review_row_count),
            format!("| High Fixed | {} |", self.high_fixed_count),
            format!("| Low Fixed | {} |", self.low_fixed_count),
            format!(
                "| Non-positive Volume | {} |",
                self.non_positive_volume_count
            ),
            format!(
                "| Non-positive Amount | {} |",
                self.non_positive_amount_count
            ),
            "".to_string(),
            "## Rule Counts".to_string(),
            "| Rule | Count |".to_string(),
            "| --- | --- |".to_string(),
            format!("| ohlc_envelope_high | {} |", self.high_fixed_count),
            format!("| ohlc_envelope_low | {} |", self.low_fixed_count),
            format!("| zero_volume | {} |", self.zero_volume_count),
            format!("| non_positive_price | {} |", self.non_positive_price_count),
            format!(
                "| non_positive_amount | {} |",
                self.non_positive_amount_flagged_count
            ),
            "".to_string(),
            "## Before/After Samples".to_string(),
        ];
        if self.diffs.is_empty() {
            lines.push("_No sampled changes._".to_string());
        } else {
            lines.push("| Code | Date | Field | Before | After | Rule | Action |".to_string());
            lines.push("| --- | --- | --- | --- | --- | --- | --- |".to_string());
            for diff in &self.diffs {
                lines.push(format!(
                    "| {} | {} | {} | {} | {} | {} | {} |",
                    md_escape(&diff.ts_code),
                    md_escape(&diff.trade_date),
                    md_escape(&diff.field),
                    md_escape(&diff.before),
                    md_escape(&diff.after),
                    md_escape(&diff.rule),
                    md_escape(&diff.action)
                ));
            }
        }
        lines.push(String::new());
        lines.join("\n")
    }
}

fn main() {
    if let Err(err) = run() {
        eprintln!("data_cleaner error: {err}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let args = parse_args(env::args().skip(1).collect())?;
    let mut policy = if let Some(config) = &args.config {
        load_policy(config)?
    } else {
        CleaningPolicy::default()
    };
    if args.no_fix_ohlc_envelope {
        policy.fix_ohlc_envelope = false;
    }
    if args.no_flag_zero_volume {
        policy.flag_zero_volume = false;
    }
    if args.no_flag_non_positive_price {
        policy.flag_non_positive_price = false;
    }
    if args.flag_non_positive_amount {
        policy.flag_non_positive_amount = true;
    }
    if let Some(limit) = args.diff_sample_limit {
        policy.diff_sample_limit = limit;
    }

    let content = fs::read_to_string(&args.input)?;
    let (cleaned, report) = clean_csv(&content, policy)?;
    write_text(&args.output, &cleaned)?;
    if let Some(report_path) = &args.report {
        write_text(report_path, &report.to_json())?;
    }
    if let Some(markdown_path) = &args.report_md {
        write_text(markdown_path, &report.to_markdown())?;
    }

    println!("Wrote cleaned daily bars to {}", args.output.display());
    if let Some(report_path) = &args.report {
        println!("Wrote cleaning report to {}", report_path.display());
    }
    if let Some(markdown_path) = &args.report_md {
        println!("Wrote cleaning Markdown to {}", markdown_path.display());
    }
    println!(
        "changed_rows={}, auto_fixed_rows={}, manual_review_rows={}",
        report.changed_row_count, report.auto_fixed_row_count, report.manual_review_row_count
    );
    Ok(())
}

fn parse_args(args: Vec<String>) -> Result<CliArgs, Box<dyn std::error::Error>> {
    if args.len() == 2 && !args[0].starts_with("--") {
        return Ok(CliArgs {
            input: PathBuf::from(&args[0]),
            output: PathBuf::from(&args[1]),
            report: None,
            report_md: None,
            config: None,
            no_fix_ohlc_envelope: false,
            no_flag_zero_volume: false,
            no_flag_non_positive_price: false,
            flag_non_positive_amount: false,
            diff_sample_limit: None,
        });
    }

    let mut input = None;
    let mut output = None;
    let mut report = None;
    let mut report_md = None;
    let mut config = None;
    let mut no_fix_ohlc_envelope = false;
    let mut no_flag_zero_volume = false;
    let mut no_flag_non_positive_price = false;
    let mut flag_non_positive_amount = false;
    let mut diff_sample_limit = None;
    let mut index = 0;
    while index < args.len() {
        match args[index].as_str() {
            "--input" => input = Some(PathBuf::from(take_value(&args, &mut index)?)),
            "--output" => output = Some(PathBuf::from(take_value(&args, &mut index)?)),
            "--report" => report = Some(PathBuf::from(take_value(&args, &mut index)?)),
            "--report-md" => report_md = Some(PathBuf::from(take_value(&args, &mut index)?)),
            "--config" => config = Some(PathBuf::from(take_value(&args, &mut index)?)),
            "--no-fix-ohlc-envelope" => no_fix_ohlc_envelope = true,
            "--no-flag-zero-volume" => no_flag_zero_volume = true,
            "--no-flag-non-positive-price" => no_flag_non_positive_price = true,
            "--flag-non-positive-amount" => flag_non_positive_amount = true,
            "--diff-sample-limit" => {
                diff_sample_limit = Some(take_value(&args, &mut index)?.parse::<usize>()?)
            }
            "--help" | "-h" => return Err(usage().into()),
            value => return Err(format!("unknown argument: {value}\n{}", usage()).into()),
        }
        index += 1;
    }

    Ok(CliArgs {
        input: input.ok_or_else(usage)?,
        output: output.ok_or_else(usage)?,
        report,
        report_md,
        config,
        no_fix_ohlc_envelope,
        no_flag_zero_volume,
        no_flag_non_positive_price,
        flag_non_positive_amount,
        diff_sample_limit,
    })
}

fn take_value(args: &[String], index: &mut usize) -> Result<String, Box<dyn std::error::Error>> {
    *index += 1;
    args.get(*index)
        .cloned()
        .ok_or_else(|| "missing argument value".into())
}

fn usage() -> String {
    concat!(
        "usage: data_cleaner <input.csv> <output.csv>\n",
        "   or: data_cleaner --input <input.csv> --output <output.csv> ",
        "[--config config/cleaning.yaml] [--report report.json] [--report-md report.md]"
    )
    .to_string()
}

fn load_policy(path: &PathBuf) -> Result<CleaningPolicy, Box<dyn std::error::Error>> {
    let content = fs::read_to_string(path)?;
    Ok(parse_policy_text(&content))
}

fn parse_policy_text(content: &str) -> CleaningPolicy {
    let mut policy = CleaningPolicy::default();
    let mut current_rule: Option<String> = None;
    for raw_line in content.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((key, value)) = line.split_once(':') {
            let key = key.trim().trim_matches('"');
            let value = value.trim().trim_matches('"');
            if key == "diff_sample_limit" {
                if let Ok(limit) = value.parse::<usize>() {
                    policy.diff_sample_limit = limit;
                }
                continue;
            }
            if value.is_empty() {
                current_rule = Some(key.to_string());
                continue;
            }
            if key == "enabled" {
                if let Some(rule) = &current_rule {
                    set_rule_enabled(&mut policy, rule, parse_bool(value));
                }
            } else {
                set_rule_enabled(&mut policy, key, parse_bool(value));
            }
        }
    }
    policy
}

fn set_rule_enabled(policy: &mut CleaningPolicy, rule: &str, enabled: bool) {
    match rule {
        "ohlc_envelope" => policy.fix_ohlc_envelope = enabled,
        "zero_volume" => policy.flag_zero_volume = enabled,
        "non_positive_price" => policy.flag_non_positive_price = enabled,
        "non_positive_amount" => policy.flag_non_positive_amount = enabled,
        _ => {}
    }
}

fn parse_bool(value: &str) -> bool {
    matches!(
        value.trim().to_ascii_lowercase().as_str(),
        "true" | "1" | "yes"
    )
}

fn clean_csv(
    content: &str,
    policy: CleaningPolicy,
) -> Result<(String, CleaningReport), Box<dyn std::error::Error>> {
    let mut lines = content.lines();
    let header = lines
        .next()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "empty csv"))?;
    let headers: Vec<&str> = header.split(',').collect();
    let index = ColumnIndex {
        ts_code: find_column(&headers, "ts_code"),
        trade_date: find_column(&headers, "trade_date"),
        open: find_column(&headers, "open"),
        high: find_column(&headers, "high"),
        low: find_column(&headers, "low"),
        close: find_column(&headers, "close"),
        volume: find_column(&headers, "volume"),
        amount: find_column(&headers, "amount"),
        quality_flag: find_column(&headers, "quality_flag"),
    };

    let mut cleaned = String::new();
    cleaned.push_str(header);
    cleaned.push('\n');

    let mut input_rows = 0;
    let mut output_rows = 0;
    let mut changed_row_count = 0;
    let mut high_fixed_count = 0;
    let mut low_fixed_count = 0;
    let mut non_positive_volume_count = 0;
    let mut non_positive_amount_count = 0;
    let mut auto_fixed_row_count = 0;
    let mut manual_review_row_count = 0;
    let mut zero_volume_count = 0;
    let mut non_positive_price_count = 0;
    let mut non_positive_amount_flagged_count = 0;
    let mut diffs = Vec::new();

    for line in lines {
        if line.trim().is_empty() {
            continue;
        }
        input_rows += 1;
        output_rows += 1;
        let mut cols: Vec<String> = line
            .split(',')
            .map(|part| part.trim().to_string())
            .collect();
        let mut row_changed = false;
        let mut row_auto_fixed = false;
        let mut row_manual_review = false;

        if let (Some(open_idx), Some(high_idx), Some(low_idx), Some(close_idx)) =
            (index.open, index.high, index.low, index.close)
        {
            let open = parse_f64(&cols, open_idx);
            let high = parse_f64(&cols, high_idx);
            let low = parse_f64(&cols, low_idx);
            let close = parse_f64(&cols, close_idx);
            if let (Some(open), Some(high), Some(low), Some(close)) = (open, high, low, close) {
                let envelope_high = open.max(high).max(low).max(close);
                let envelope_low = open.min(high).min(low).min(close);
                if policy.fix_ohlc_envelope && envelope_high > high {
                    push_value_diff(
                        &cols,
                        &index,
                        &mut diffs,
                        policy.diff_sample_limit,
                        "high",
                        high,
                        envelope_high,
                        "ohlc_envelope",
                        "AUTO_FIX",
                    );
                    cols[high_idx] = envelope_high.to_string();
                    high_fixed_count += 1;
                    row_changed = true;
                    row_auto_fixed = true;
                }
                if policy.fix_ohlc_envelope && envelope_low < low {
                    push_value_diff(
                        &cols,
                        &index,
                        &mut diffs,
                        policy.diff_sample_limit,
                        "low",
                        low,
                        envelope_low,
                        "ohlc_envelope",
                        "AUTO_FIX",
                    );
                    cols[low_idx] = envelope_low.to_string();
                    low_fixed_count += 1;
                    row_changed = true;
                    row_auto_fixed = true;
                }
                if policy.flag_non_positive_price
                    && (open <= 0.0 || high <= 0.0 || low <= 0.0 || close <= 0.0)
                    && set_quality_flag(
                        &mut cols,
                        &index,
                        &mut diffs,
                        policy.diff_sample_limit,
                        "MANUAL_REVIEW",
                        "non_positive_price",
                    )
                {
                    non_positive_price_count += 1;
                    row_changed = true;
                    row_manual_review = true;
                }
            }
        }

        if let Some(volume_idx) = index.volume {
            if parse_f64(&cols, volume_idx).unwrap_or(0.0) <= 0.0 {
                non_positive_volume_count += 1;
                if policy.flag_zero_volume
                    && set_quality_flag(
                        &mut cols,
                        &index,
                        &mut diffs,
                        policy.diff_sample_limit,
                        "ZERO_VOLUME",
                        "zero_volume",
                    )
                {
                    zero_volume_count += 1;
                    row_changed = true;
                    row_manual_review = true;
                }
            }
        }

        if let Some(amount_idx) = index.amount {
            if parse_f64(&cols, amount_idx).unwrap_or(0.0) <= 0.0 {
                non_positive_amount_count += 1;
                if policy.flag_non_positive_amount
                    && set_quality_flag(
                        &mut cols,
                        &index,
                        &mut diffs,
                        policy.diff_sample_limit,
                        "MANUAL_REVIEW",
                        "non_positive_amount",
                    )
                {
                    non_positive_amount_flagged_count += 1;
                    row_changed = true;
                    row_manual_review = true;
                }
            }
        }

        if row_changed {
            changed_row_count += 1;
        }
        if row_auto_fixed {
            auto_fixed_row_count += 1;
        }
        if row_manual_review {
            manual_review_row_count += 1;
        }
        cleaned.push_str(&cols.join(","));
        cleaned.push('\n');
    }

    Ok((
        cleaned,
        CleaningReport {
            input_rows,
            output_rows,
            changed_row_count,
            high_fixed_count,
            low_fixed_count,
            non_positive_volume_count,
            non_positive_amount_count,
            auto_fixed_row_count,
            manual_review_row_count,
            zero_volume_count,
            non_positive_price_count,
            non_positive_amount_flagged_count,
            policy,
            diffs,
        },
    ))
}

fn find_column(headers: &[&str], name: &str) -> Option<usize> {
    headers.iter().position(|header| *header == name)
}

fn parse_f64(cols: &[String], index: usize) -> Option<f64> {
    cols.get(index)?.parse::<f64>().ok()
}

fn set_quality_flag(
    cols: &mut [String],
    index: &ColumnIndex,
    diffs: &mut Vec<CleaningDiff>,
    limit: usize,
    after: &str,
    rule: &str,
) -> bool {
    let Some(flag_idx) = index.quality_flag else {
        return false;
    };
    if cols.get(flag_idx).map(|value| value.as_str()) == Some(after) {
        return false;
    }
    push_flag_diff(cols, index, diffs, limit, after, rule);
    cols[flag_idx] = after.to_string();
    true
}

fn push_value_diff(
    cols: &[String],
    index: &ColumnIndex,
    diffs: &mut Vec<CleaningDiff>,
    limit: usize,
    field: &str,
    before: f64,
    after: f64,
    rule: &str,
    action: &str,
) {
    if diffs.len() >= limit {
        return;
    }
    diffs.push(CleaningDiff {
        ts_code: column_value(cols, index.ts_code),
        trade_date: column_value(cols, index.trade_date),
        field: field.to_string(),
        before: before.to_string(),
        after: after.to_string(),
        rule: rule.to_string(),
        action: action.to_string(),
    });
}

fn push_flag_diff(
    cols: &[String],
    index: &ColumnIndex,
    diffs: &mut Vec<CleaningDiff>,
    limit: usize,
    after: &str,
    rule: &str,
) {
    if diffs.len() >= limit {
        return;
    }
    diffs.push(CleaningDiff {
        ts_code: column_value(cols, index.ts_code),
        trade_date: column_value(cols, index.trade_date),
        field: "quality_flag".to_string(),
        before: column_value(cols, index.quality_flag),
        after: after.to_string(),
        rule: rule.to_string(),
        action: "MANUAL_REVIEW".to_string(),
    });
}

fn column_value(cols: &[String], index: Option<usize>) -> String {
    index
        .and_then(|idx| cols.get(idx))
        .cloned()
        .unwrap_or_default()
}

fn write_text(path: &PathBuf, content: &str) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut file = fs::File::create(path)?;
    file.write_all(content.as_bytes())?;
    Ok(())
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

    #[test]
    fn cleans_ohlc_and_flags_zero_volume() {
        let input = concat!(
            "ts_code,trade_date,open,high,low,close,volume,amount,quality_flag\n",
            "000001.SZ,2024-01-02,10,9,11,10.5,0,0,NORMAL\n"
        );
        let (cleaned, report) = clean_csv(input, CleaningPolicy::default()).unwrap();

        assert!(cleaned.contains("000001.SZ,2024-01-02,10,11,9,10.5,0,0,ZERO_VOLUME"));
        assert_eq!(report.high_fixed_count, 1);
        assert_eq!(report.low_fixed_count, 1);
        assert_eq!(report.zero_volume_count, 1);
        assert_eq!(report.changed_row_count, 1);
        assert_eq!(report.auto_fixed_row_count, 1);
        assert_eq!(report.manual_review_row_count, 1);
        assert_eq!(report.diffs[0].action, "AUTO_FIX");
    }

    #[test]
    fn respects_disabled_ohlc_policy() {
        let input = concat!(
            "ts_code,trade_date,open,high,low,close,volume,amount,quality_flag\n",
            "000001.SZ,2024-01-02,10,9,11,10.5,100,1000,NORMAL\n"
        );
        let policy = CleaningPolicy {
            fix_ohlc_envelope: false,
            ..CleaningPolicy::default()
        };
        let (cleaned, report) = clean_csv(input, policy).unwrap();

        assert!(cleaned.contains("000001.SZ,2024-01-02,10,9,11,10.5,100,1000,NORMAL"));
        assert_eq!(report.high_fixed_count, 0);
        assert_eq!(report.low_fixed_count, 0);
        assert_eq!(report.changed_row_count, 0);
    }

    #[test]
    fn parses_yaml_like_policy() {
        let policy = parse_policy_text(
            r#"
cleaning:
  diff_sample_limit: 3
  rules:
    ohlc_envelope:
      enabled: false
    zero_volume:
      enabled: false
    non_positive_amount:
      enabled: true
"#,
        );

        assert!(!policy.fix_ohlc_envelope);
        assert!(!policy.flag_zero_volume);
        assert!(policy.flag_non_positive_amount);
        assert_eq!(policy.diff_sample_limit, 3);
    }
}
