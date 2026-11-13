"""Evaluation metrics from the proposal (section 6): forecast error, shortage-risk performance,
donor-matching correctness. Everything here is computed from stored data on request; nothing is
hard-coded. Demand data is synthetic, so these measure the pipeline, not clinical validity."""
import numpy as np
import pandas as pd

from .donor_matching import COMPATIBLE_DONORS, DONATION_COOLDOWN_DAYS, days_since, match_donors
from .forecasting import backtest_metrics, sarima_evaluate, simple_exponential_smoothing
from .risk import assess_risk

# Independent copy of the SRS compatibility table, used as the oracle when verifying the service.
SRS_COMPATIBILITY = {
    "O-": ["O-"], "O+": ["O-", "O+"], "A-": ["O-", "A-"], "A+": ["O-", "O+", "A-", "A+"],
    "B-": ["O-", "B-"], "B+": ["O-", "O+", "B-", "B+"], "AB-": ["O-", "A-", "B-", "AB-"],
    "AB+": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
}


def forecast_table(series_by_group: dict, include_sarima: bool = False) -> dict:
    rows = []
    for g, s in sorted(series_by_group.items()):
        if len(s) < 30:
            continue
        m = backtest_metrics(s)
        cands = [("naive_baseline", m["mae_baseline"], m["rmse_baseline"]), ("exp_smoothing", m["mae_ses"], m["rmse_ses"])]
        if include_sarima:
            sar = sarima_evaluate(s)
            if sar:
                cands.append(("sarima", sar["mae"], sar["rmse"]))
        best = min(cands, key=lambda c: c[1])
        base = cands[0][1]
        rows.append({
            "blood_group": g, "selected": best[0], "backtest_days": m["days"],
            "improvement_pct": round(100 * (base - best[1]) / base, 1) if base > 0 else None,
            "models": [{"name": n, "mae": round(float(a), 2), "rmse": round(float(r), 2)} for n, a, r in cands],
        })
    summary = {}
    if rows:
        summary = {
            "groups": len(rows),
            "mean_mae_baseline": round(float(np.mean([r["models"][0]["mae"] for r in rows])), 2),
            "mean_mae_selected": round(float(np.mean([min(m["mae"] for m in r["models"]) for r in rows])), 2),
            "mean_rmse_selected": round(float(np.mean([next(m["rmse"] for m in r["models"] if m["name"] == r["selected"]) for r in rows])), 2),
        }
    return {"rows": rows, "summary": summary}


def shortage_detection(series_by_group: dict, multipliers=(0.7, 0.8, 0.9, 1.1, 1.2, 1.3), origins: int = 15, horizon: int = 7) -> dict:
    """How well do forecast + the risk rule flag real shortages?

    For each blood group and each of the last `origins` forecast origins t, forecast the next `horizon`
    days from data BEFORE t only, then compare with what actually happened. Historical stock is not
    recorded, so stock is simulated as a multiple of the actual demand: below 1x is a true shortage,
    above 1x is not. A case is 'flagged' when the rule says MODERATE or HIGH."""
    tp = fp = tn = fn = high_n = high_hit = 0
    for g, s in series_by_group.items():
        v = s.to_numpy(float)
        n = len(v)
        if n < horizon + origins + 15:
            continue
        for t in range(n - horizon - origins + 1, n - horizon + 1):
            pred = round(simple_exponential_smoothing(pd.Series(v[:t])) * horizon, 1)
            actual = float(v[t:t + horizon].sum())
            for m in multipliers:
                stock = int(round(m * actual))
                truth = actual > stock
                level = assess_risk(stock, pred)["risk_level"]
                flagged = level != "LOW"
                tp += truth and flagged
                fp += (not truth) and flagged
                fn += truth and not flagged
                tn += (not truth) and not flagged
                if level == "HIGH":
                    high_n += 1
                    high_hit += truth
    total = tp + fp + tn + fn
    div = lambda a, b: round(a / b, 3) if b else None
    p, r = div(tp, tp + fp), div(tp, tp + fn)
    return {
        "cases": int(total), "confusion": {"tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn)},
        "precision": p, "recall": r, "accuracy": div(tp + tn, total),
        "f1": round(2 * p * r / (p + r), 3) if p and r else None,
        "high_precision": div(high_hit, high_n), "multipliers": list(multipliers), "origins": origins, "horizon_days": horizon,
        "protocol": "Forecast uses only earlier data (exponential smoothing). Stock is simulated at 0.7x to 1.3x of actual demand because historical stock isn't recorded.",
    }


def verify_matching(donors: list, match_fn=match_donors) -> dict:
    """Check match_donors against the SRS rules, computed independently, for every blood group."""
    violations, omissions, exclusions, examples = 0, 0, {"unavailable": 0, "no_consent": 0, "cooldown": 0}, []
    for target, allowed in SRS_COMPATIBILITY.items():
        expected = set()
        for d in donors:
            if d["blood_group"] not in allowed:
                continue
            if not d["is_available"]:
                exclusions["unavailable"] += 1
            elif not d["notification_consent"]:
                exclusions["no_consent"] += 1
            elif days_since(d["last_donation_date"]) < DONATION_COOLDOWN_DAYS:
                exclusions["cooldown"] += 1
            else:
                expected.add(d["donor_id"])
        got = {m["donor_id"] for m in match_fn(target, donors)}
        for bad in got - expected:
            violations += 1
            examples.append(f"{target}: returned donor {bad} who breaks a rule")
        for miss in expected - got:
            omissions += 1
            examples.append(f"{target}: omitted eligible donor {miss}")
    table_ok = all(set(COMPATIBLE_DONORS.get(g, [])) == set(a) for g, a in SRS_COMPATIBILITY.items())
    return {
        "targets_checked": len(SRS_COMPATIBILITY), "donors": len(donors), "violations": violations, "omissions": omissions,
        "compatibility_table_matches_srs": table_ok, "excluded_compatible_donors": exclusions,
        "passed": violations == 0 and omissions == 0 and table_ok, "examples": examples[:5],
    }
