from __future__ import annotations

from pathlib import Path

from quant.core.models import StrategyAdmissionDecision, StrategyRegistration


PAPER_ALLOWED_STATUSES = {"paper", "production"}


class StrategyAdmissionPolicy:
    def __init__(
        self,
        *,
        allowed_statuses: set[str] | None = None,
        require_research_report: bool = True,
        require_existing_report: bool = True,
    ) -> None:
        self.allowed_statuses = allowed_statuses or PAPER_ALLOWED_STATUSES
        self.require_research_report = require_research_report
        self.require_existing_report = require_existing_report

    def check(self, registration: StrategyRegistration) -> StrategyAdmissionDecision:
        reasons: list[str] = []
        if registration.status not in self.allowed_statuses:
            reasons.append(f"strategy status '{registration.status}' is not allowed")
        if self.require_research_report and not registration.research_report_path:
            reasons.append("research_report_path is required")
        if (
            self.require_research_report
            and self.require_existing_report
            and registration.research_report_path
            and not Path(registration.research_report_path).exists()
        ):
            reasons.append(f"research report does not exist: {registration.research_report_path}")

        return StrategyAdmissionDecision.reject(*reasons) if reasons else StrategyAdmissionDecision.allow()
