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
import os
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


def backtest_metrics(series: pd.Series, alpha: float = 0.3, holdout: int = 14) -> dict:
    """Chronological rolling-origin backtest (each forecast only sees data
    strictly before the day it predicts, so there is no leakage). Reports MAE
    and RMSE for the baseline and for SES over the last `holdout` days."""
    values = series.to_numpy(dtype=float)
    n = len(values)
    start = max(15, n - holdout)
    eb, es = [], []
    for i in range(start, n):
        history = pd.Series(values[:i])
        eb.append(naive_baseline_forecast(history) - values[i])
        es.append(simple_exponential_smoothing(history, alpha) - values[i])
    if not eb:
        return {"mae_baseline": float("nan"), "mae_ses": float("nan"),
                "rmse_baseline": float("nan"), "rmse_ses": float("nan"), "days": 0}
    eb, es = np.array(eb), np.array(es)
    return {
        "mae_baseline": float(np.mean(np.abs(eb))), "mae_ses": float(np.mean(np.abs(es))),
        "rmse_baseline": float(np.sqrt(np.mean(eb ** 2))), "rmse_ses": float(np.sqrt(np.mean(es ** 2))),
        "days": len(eb),
    }


# ---------------------------------------------------------------------------
# SARIMA candidate (weekly seasonality). statsmodels is an optional dependency:
# if it is missing, disabled (BLOODLINE_SARIMA=0) or fails to fit, the pipeline
# silently falls back to baseline + exponential smoothing.
# ---------------------------------------------------------------------------
SARIMA_NAME = "sarima"
SARIMA_ORDER = (1, 0, 1)
SARIMA_SEASONAL = (1, 0, 1, 7)
SARIMA_MIN_OBS = 60       # need several weekly cycles to estimate the seasonal terms
SARIMA_MAX_HORIZON = 60
_sarima_cache: dict = {}  # fitting takes a moment, so reuse results while the data is unchanged


def sarima_available() -> bool:
    if os.getenv("BLOODLINE_SARIMA", "1") == "0":
        return False
    try:
        import statsmodels.tsa.statespace.sarimax  # noqa: F401
    except Exception:
        return False
    return True


def sarima_evaluate(series: pd.Series, holdout: int = 14):
    """Chronological evaluation + forecast for SARIMA, or None if unavailable.

    No leakage: parameters are fitted on data BEFORE the holdout only. The fitted
    model is then run over the whole series with those parameters frozen, so each
    one-step-ahead prediction for a holdout day uses only earlier observations
    (the same one-step-ahead protocol used for the baseline and SES). A second
    fit on the full history produces the actual forecast."""
    values = series.to_numpy(dtype=float)
    n = len(values)
    if n < SARIMA_MIN_OBS or not sarima_available():
        return None
    key = (n, round(float(values.sum()), 3), round(float(values[-1]), 3))
    if key in _sarima_cache:
        return _sarima_cache[key]
    try:
        import warnings
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        start = max(15, n - holdout)
        kw = dict(order=SARIMA_ORDER, seasonal_order=SARIMA_SEASONAL,
                  enforce_stationarity=False, enforce_invertibility=False)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            train_fit = SARIMAX(values[:start], **kw).fit(disp=False, maxiter=50)
            frozen = train_fit.apply(values, refit=False)
            pred = np.asarray(frozen.get_prediction(start=start, end=n - 1).predicted_mean, dtype=float)
            full_fit = SARIMAX(values, **kw).fit(disp=False, maxiter=50)
            fc = np.clip(np.asarray(full_fit.forecast(SARIMA_MAX_HORIZON), dtype=float), 0, None)
        err = pred - values[start:]
        if not (np.all(np.isfinite(err)) and np.all(np.isfinite(fc))) or len(err) == 0:
            return None
        out = {"mae": float(np.mean(np.abs(err))), "rmse": float(np.sqrt(np.mean(err ** 2))),
               "forecast": fc, "days": len(err)}
    except Exception:
        return None
    if len(_sarima_cache) > 256:
        _sarima_cache.clear()
    _sarima_cache[key] = out
    return out


# On equal backtest MAE, prefer exponential smoothing, then the baseline, then SARIMA
# (this keeps the earlier two-model behaviour unchanged when SARIMA is unavailable).
_TIE_ORDER = {"exp_smoothing": 0, "naive_baseline": 1, SARIMA_NAME: 2}


def select_model(candidates: list) -> dict:
    """Pick the candidate with the lowest backtest MAE; NaN candidates are ignored."""
    valid = [c for c in candidates if c["mae"] is not None and np.isfinite(c["mae"])]
    if not valid:
        return next(c for c in candidates if c["name"] == "naive_baseline")
    return min(valid, key=lambda c: (c["mae"], _TIE_ORDER.get(c["name"], 9)))


def forecast_demand(df: pd.DataFrame, horizon_days: int = 7, use_sarima: bool = True) -> dict:
    """
    df: DataFrame with columns [date, units_demanded].
    Compares a moving-average baseline, simple exponential smoothing and (when
    statsmodels is installed) SARIMA on the same chronological backtest, then
    forecasts with the model that has the lowest MAE. All candidates and their
    MAE/RMSE are returned so the choice is explainable.
    """
    df = df.sort_values("date")
    series = df["units_demanded"]

    baseline_daily = naive_baseline_forecast(series)
    ses_daily = simple_exponential_smoothing(series)
    m = backtest_metrics(series)
    mae_baseline, mae_ses = m["mae_baseline"], m["mae_ses"]

    def r(x):
        return round(float(x), 2) if x is not None and np.isfinite(x) else None

    candidates = [
        {"name": "naive_baseline", "mae": mae_baseline, "rmse": m["rmse_baseline"], "total": baseline_daily * horizon_days},
        {"name": "exp_smoothing", "mae": mae_ses, "rmse": m["rmse_ses"], "total": ses_daily * horizon_days},
    ]
    sar = sarima_evaluate(series) if (use_sarima and horizon_days <= SARIMA_MAX_HORIZON) else None
    if sar is not None:
        candidates.append({"name": SARIMA_NAME, "mae": sar["mae"], "rmse": sar["rmse"],
                           "total": float(sar["forecast"][:horizon_days].sum())})

    chosen = select_model(candidates)
    improvement_pct = None
    if np.isfinite(mae_baseline) and mae_baseline > 0 and np.isfinite(chosen["mae"]):
        improvement_pct = round(100 * (mae_baseline - chosen["mae"]) / mae_baseline, 1)

    return {
        "model_name": chosen["name"],
        "horizon_days": horizon_days,
        "predicted_units": round(chosen["total"], 1),
        "baseline_units": round(baseline_daily * horizon_days, 1),
        "baseline_model_name": "naive_baseline",
        "improvement_over_baseline_pct": improvement_pct,
        "mae_baseline": r(mae_baseline),
        "mae_candidate": r(mae_ses),
        "rmse_baseline": r(m["rmse_baseline"]) if m["days"] else None,
        "rmse_candidate": r(m["rmse_ses"]) if m["days"] else None,
        "backtest_days": m["days"],
        "selected_mae": r(chosen["mae"]),
        "candidates": [
            {"name": c["name"], "mae": r(c["mae"]), "rmse": r(c["rmse"]),
             "predicted_units": round(c["total"], 1), "selected": c["name"] == chosen["name"]}
            for c in candidates
        ],
    }
