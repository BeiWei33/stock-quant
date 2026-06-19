from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from quant.core.research.alpha_validation import AlphaValidationResult


@dataclass(frozen=True)
class ResearchReportPaths:
    json_path: Path
    markdown_path: Path


class AlphaResearchReportWriter:
    def write(self, result: AlphaValidationResult, output_dir: Path) -> ResearchReportPaths:
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{result.factor_name}_h{result.horizon}"
        json_path = output_dir / f"{stem}.json"
        markdown_path = output_dir / f"{stem}.md"

        json_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(self.render_markdown(result), encoding="utf-8")
        return ResearchReportPaths(json_path=json_path, markdown_path=markdown_path)

    def render_markdown(self, result: AlphaValidationResult) -> str:
        summary = result.summary
        lines = [
            f"# Alpha Research Report: {result.factor_name}",
            "",
            "## Setup",
            "",
            f"- Factor: `{result.factor_name}`",
            f"- Forward return horizon: `{result.horizon}` trading days",
            f"- Quantiles: `{result.quantiles}`",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
        ]
        for key in [
            "ic_mean",
            "icir",
            "rank_ic_mean",
            "rank_icir",
            "rank_ic_positive_rate",
            "sample_days",
            "top_group_return_mean",
            "bottom_group_return_mean",
            "long_short_return_mean",
            "group_monotonicity",
            "top_quantile_turnover_mean",
            "oos_rank_ic_mean",
            "oos_rank_icir",
            "oos_long_short_return_mean",
            "rank_ic_train_test_delta",
            "long_short_train_test_delta",
        ]:
            lines.append(f"| {key} | {summary.get(key, 0.0):.6f} |")

        lines.extend(["", "## Train/Test Split", ""])
        lines.extend(
            [
                "| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for label in ["train", "test"]:
            split = result.split_summary.get(label, {})
            lines.append(
                "| {period} | {start} | {end} | {days:.0f} | {rank_ic:.6f} | {rank_icir:.6f} | {long_short:.6f} | {turnover:.6f} |".format(
                    period=label,
                    start=split.get("start_date", ""),
                    end=split.get("end_date", ""),
                    days=float(split.get("sample_days", 0.0)),
                    rank_ic=float(split.get("rank_ic_mean", 0.0)),
                    rank_icir=float(split.get("rank_icir", 0.0)),
                    long_short=float(split.get("long_short_return_mean", 0.0)),
                    turnover=float(split.get("top_quantile_turnover_mean", 0.0)),
                )
            )

        lines.extend(["", "## Average Group Forward Return", "", "| Quantile | Mean Return |", "| ---: | ---: |"])
        if result.group_returns.empty:
            lines.append("| n/a | 0.000000 |")
        else:
            group_mean = result.group_returns.groupby("quantile")["mean_forward_return"].mean()
            for quantile, value in group_mean.items():
                lines.append(f"| {int(quantile)} | {float(value):.6f} |")

        lines.extend(["", "## Review Notes", ""])
        lines.extend(
            [
                "- This report is a statistical research artifact, not a production approval.",
                "- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.",
                "- Negative or unstable Rank IC should trigger review rather than automatic deployment.",
            ]
        )
        lines.append("")
        return "\n".join(lines)
