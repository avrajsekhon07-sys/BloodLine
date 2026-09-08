"""
Synthetic blood-demand data generator.

IMPORTANT: this data is SIMULATED. It exists only because the prototype has
no access to granular real blood-bank consumption data. It must never be
presented to a user as real hospital statistics — every API response that
serves it is tagged is_synthetic=True.

Demand(day) = baseline + weekly_pattern + seasonal_effect + emergency_spike + noise

- baseline: differs per blood group (O+ and A+ run higher baseline demand
  than AB- etc., mirroring real population blood-type distribution).
- weekly_pattern: demand is lower on weekends, higher midweek (elective
  surgery scheduling), matching typical hospital demand cycles.
- seasonal_effect: a slow sinusoidal component plus a holiday-window bump
  (e.g. accident/trauma spikes around festival/holiday periods).
- emergency_spike: rare, large one-off spikes (mass casualty events,
  local emergencies) injected at low probability.
- noise: bounded Gaussian noise so no two days are identical.
"""
import numpy as np
import pandas as pd

BLOOD_GROUP_BASELINE = {
    "O+": 18.0, "A+": 15.0, "B+": 13.0, "AB+": 5.0,
    "O-": 7.0, "A-": 6.0, "B-": 5.0, "AB-": 2.5,
}

HOLIDAY_DOYS = [1, 50, 100, 150, 200, 250, 300, 350]  # illustrative recurring spike windows


def generate_demand_series(blood_group: str, start_date: str, days: int = 180, seed: int = None) -> pd.DataFrame:
    """Return a DataFrame with columns [date, units_demanded] of synthetic demand."""
    rng = np.random.default_rng(seed if seed is not None else abs(hash(blood_group)) % (2**32))
    dates = pd.date_range(start=start_date, periods=days, freq="D")
    baseline = BLOOD_GROUP_BASELINE.get(blood_group, 8.0)

    day_of_week = dates.dayofweek.to_numpy()  # 0=Mon ... 6=Sun
    weekly_pattern = np.where(day_of_week >= 5, -0.18, 0.10) * baseline  # weekends lower

    day_of_year = dates.dayofyear.to_numpy()
    seasonal = 0.12 * baseline * np.sin(2 * np.pi * day_of_year / 365.0)

    holiday_bump = np.zeros(days)
    for doy in HOLIDAY_DOYS:
        window = np.abs(day_of_year - doy) <= 2
        holiday_bump[window] += baseline * 0.35

    emergency_spike = np.zeros(days)
    spike_days = rng.random(days) < 0.02  # ~2% of days
    emergency_spike[spike_days] = baseline * rng.uniform(0.8, 1.8, size=spike_days.sum())

    noise = rng.normal(loc=0, scale=baseline * 0.08, size=days)

    demand = baseline + weekly_pattern + seasonal + holiday_bump + emergency_spike + noise
    demand = np.clip(demand, a_min=0, a_max=None)
    demand = np.round(demand, 1)

    return pd.DataFrame({"date": dates.date, "units_demanded": demand})


def generate_all_groups(start_date: str, days: int = 180) -> dict:
    return {bg: generate_demand_series(bg, start_date, days) for bg in BLOOD_GROUP_BASELINE}
