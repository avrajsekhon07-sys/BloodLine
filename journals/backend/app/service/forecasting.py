"""
Forecasting pipeline for near-term blood demand.

We deliberately do NOT claim a novel forecasting algorithm. For the W5
prototype we implement two candidate methods and always report the
candidate model alongside the baseline it's being evaluated against:

  - baseline: naive/moving-average forecast (mean of last N days)
  - candidate: simple exponential smoothing (SES) — a standard,
    well-understood time-series method, implemented directly with
    numpy/pandas so the prototype has no heavy ML dependency.

For the EST/final version this module can be swapped to use
statsmodels/Prophet without changing the API contract (predict_demand
always returns predicted_units + baseline_units + which one is "better").
"""
from typing import Tuple
import numpy as np
import pandas as pd


def naive_baseline_forecast(series: pd.Series, window: int = 14) -> float:
    """Average of the last `window` observed days — the baseline every
    candidate model must beat to be worth using."""
    return float(series.tail(window).mean())


def simple_exponential_smoothing(series: pd.Series, alpha: float = 0.3) -> float:
    """One-step-ahead SES forecast. Returns the smoothed level, which is
    the forecast for the next period; for a multi-day horizon we hold it
    flat across the horizon (reasonable for short-term demand)."""
    values = series.to_numpy(dtype=float)
    level = values[0]
    for v in values[1:]:
        level = alpha * v + (1 - alpha) * level
    return float(level)


def backtest_mae(series: pd.Series, alpha: float = 0.3, holdout: int = 14) -> Tuple[float, float]:
    """Rolling-origin backtest over the last `holdout` days: returns
    (mae_baseline, mae_ses) so we can honestly report whether SES beats
    the naive baseline on this specific blood group's history."""
    errors_baseline, errors_ses = [], []
    values = series.to_numpy(dtype=float)
    n = len(values)
    start = max(15, n - holdout)
    for i in range(start, n):
        history = pd.Series(values[:i])
        actual = values[i]
        errors_baseline.append(abs(naive_baseline_forecast(history) - actual))
        errors_ses.append(abs(simple_exponential_smoothing(history) - actual))
    mae_baseline = float(np.mean(errors_baseline)) if errors_baseline else float("nan")
    mae_ses = float(np.mean(errors_ses)) if errors_ses else float("nan")
    return mae_baseline, mae_ses


def forecast_demand(df: pd.DataFrame, horizon_days: int = 7) -> dict:
    """
    df: DataFrame with columns [date, units_demanded], chronologically sorted.
    Returns predicted total demand over horizon_days for both baseline and
    the candidate model, plus which one the backtest favors.
    """
    df = df.sort_values("date")
    series = df["units_demanded"]

    baseline_daily = naive_baseline_forecast(series)
    ses_daily = simple_exponential_smoothing(series)

    mae_baseline, mae_ses = backtest_mae(series)
    better_model = "exp_smoothing" if mae_ses <= mae_baseline else "naive_baseline"
    chosen_daily = ses_daily if better_model == "exp_smoothing" else baseline_daily

    improvement_pct = None
    if mae_baseline and not np.isnan(mae_baseline) and mae_baseline > 0:
        improvement_pct = round(100 * (mae_baseline - mae_ses) / mae_baseline, 1)

    return {
        "model_name": better_model,
        "horizon_days": horizon_days,
        "predicted_units": round(chosen_daily * horizon_days, 1),
        "baseline_units": round(baseline_daily * horizon_days, 1),
        "baseline_model_name": "naive_baseline",
        "improvement_over_baseline_pct": improvement_pct,
        "mae_baseline": round(mae_baseline, 2) if not np.isnan(mae_baseline) else None,
        "mae_candidate": round(mae_ses, 2) if not np.isnan(mae_ses) else None,
    }
