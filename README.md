"""
workflow_simulator.py
------------------------
NOTE ON SCOPE: Appian is a licensed, proprietary low-code BPM platform. This
module is an open-source stand-in that reproduces the *case-management
pattern* an Appian application would implement - a defined state machine,
SLA timers, and an auditable case log - so the pipeline is runnable end to
end without an enterprise license. If you have real Appian access, replace
this with an Appian process model that consumes the same input file
(outputs/aml_flagged_transactions.csv) via its integration connector.

States: DETECTED -> ASSIGNED -> UNDER_REVIEW -> {ESCALATED | CLEARED}
Each case gets a synthetic reviewer, an SLA deadline, and a resolution based
on how anomalous it is (higher anomaly_score -> more likely escalated).
"""
import random
from dataclasses import dataclass, field
from datetime import timedelta

import pandas as pd

REVIEWERS = ["A. Menon", "R. Castillo", "J. Okafor", "S. Iyer", "T. Nakamura"]
SLA_HOURS = {"DETECTED": 1, "ASSIGNED": 4, "UNDER_REVIEW": 24}


@dataclass
class Case:
    case_id: str
    event_id: str
    anomaly_score: float
    state: str = "DETECTED"
    reviewer: str = None
    history: list = field(default_factory=list)


def run_workflow(flagged_csv: str, seed: int = 7) -> pd.DataFrame:
    random.seed(seed)
    df = pd.read_csv(flagged_csv)
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", errors="coerce")

    cases = []
    for i, row in df.iterrows():
        case = Case(case_id=f"CASE-{i:05d}", event_id=row["event_id"], anomaly_score=row["anomaly_score"])
        t0 = row["timestamp"] if pd.notna(row["timestamp"]) else pd.Timestamp("2025-01-01")
        case.history.append(("DETECTED", t0))

        assign_t = t0 + timedelta(hours=random.uniform(0.2, SLA_HOURS["DETECTED"]))
        case.reviewer = random.choice(REVIEWERS)
        case.history.append(("ASSIGNED", assign_t))

        review_t = assign_t + timedelta(hours=random.uniform(0.5, SLA_HOURS["ASSIGNED"]))
        case.history.append(("UNDER_REVIEW", review_t))

        # higher anomaly score -> higher chance of escalation to compliance
        escalate_prob = min(0.15 + case.anomaly_score * 0.6, 0.9)
        resolved_t = review_t + timedelta(hours=random.uniform(1, SLA_HOURS["UNDER_REVIEW"]))
        final_state = "ESCALATED" if random.random() < escalate_prob else "CLEARED"
        case.history.append((final_state, resolved_t))
        case.state = final_state

        cases.append(case)

    rows = []
    for c in cases:
        total_cycle_hours = (c.history[-1][1] - c.history[0][1]).total_seconds() / 3600
        rows.append(
            {
                "case_id": c.case_id,
                "event_id": c.event_id,
                "reviewer": c.reviewer,
                "final_state": c.state,
                "anomaly_score": c.anomaly_score,
                "cycle_time_hours": round(total_cycle_hours, 2),
                "sla_breached": total_cycle_hours > sum(SLA_HOURS.values()),
            }
        )
    return pd.DataFrame(rows)


def run(flagged_csv: str) -> dict:
    cases = run_workflow(flagged_csv)
    cases.to_csv("outputs/appian_case_log.csv", index=False)
    return {
        "total_cases_opened": len(cases),
        "escalated_to_compliance": int((cases["final_state"] == "ESCALATED").sum()),
        "cleared": int((cases["final_state"] == "CLEARED").sum()),
        "sla_breaches": int(cases["sla_breached"].sum()),
        "avg_cycle_time_hours": round(float(cases["cycle_time_hours"].mean()), 2),
        "reviewer_caseload": cases["reviewer"].value_counts().to_dict(),
    }


if __name__ == "__main__":
    print(run("outputs/aml_flagged_transactions.csv"))
