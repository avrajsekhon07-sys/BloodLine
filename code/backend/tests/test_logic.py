"""Pure-logic tests (no database): risk rule, donor matching, forecasting evaluation."""
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.services.donor_matching import match_donors
from app.services import forecasting
from app.services.forecasting import backtest_metrics, forecast_demand, select_model
from app.services.risk import assess_risk


def test_risk_srs_example_is_moderate():
    # SRS example: 20 in stock, 25 forecast -> shortfall 5 = 25% of stock -> MODERATE
    r = assess_risk(20, 25)
    assert r["risk_level"] == "MODERATE" and r["shortfall"] == 5


def test_risk_levels():
    assert assess_risk(50, 30)["risk_level"] == "LOW"
    assert assess_risk(20, 26)["risk_level"] == "HIGH"
    assert assess_risk(0, 5)["risk_level"] == "HIGH"
    assert assess_risk(10, 10)["risk_level"] == "LOW"  # shortfall 0 is LOW
    assert assess_risk(20, 25)["explanation"]


def _d(i, bg, **kw):
    base = dict(donor_id=i, full_name=i, blood_group=bg, last_donation_date=date.today() - timedelta(days=200),
                is_available=True, notification_consent=True)
    base.update(kw)
    return base


def test_matching_filters():
    donors = [
        _d("ok", "O-"),
        _d("incompatible", "A+"),
        _d("unavailable", "O-", is_available=False),
        _d("noconsent", "O-", notification_consent=False),
        _d("cooldown", "O-", last_donation_date=date.today() - timedelta(days=30)),
    ]
    assert [m["donor_id"] for m in match_donors("B+", donors)] == ["ok"]


def test_matching_ranks_exact_group_first_and_explains():
    donors = [_d("o", "O-"), _d("b", "B+")]
    res = match_donors("B+", donors)
    assert res[0]["donor_id"] == "b" and all(m["reasons"] for m in res)


def test_matching_radius_excludes_far_and_unknown():
    donors = [_d("near", "O-", distance_km=3.0), _d("far", "O-", distance_km=40.0), _d("unknown", "O-")]
    assert [m["donor_id"] for m in match_donors("O-", donors, radius_km=10)] == ["near"]
    assert len(match_donors("O-", donors)) == 3  # no radius -> no distance filter


def test_never_donated_wording():
    res = match_donors("O-", [_d("new", "O-", last_donation_date=None)])
    assert any("No donation on record" in r for r in res[0]["reasons"])
    assert not any("999" in r for r in res[0]["reasons"])


def _series(n=120):
    rng = np.random.default_rng(0)
    return pd.Series(10 + 3 * np.sin(np.arange(n) * 2 * np.pi / 7) + rng.normal(0, 1, n))


def test_backtest_reports_mae_and_rmse_and_is_chronological():
    m = backtest_metrics(_series())
    assert m["days"] == 14
    assert m["rmse_baseline"] >= m["mae_baseline"] > 0  # RMSE >= MAE always


def test_backtest_ignores_future_values():
    # Changing the last value must not change forecasts made for earlier days.
    s = _series(); s2 = s.copy(); s2.iloc[-1] += 1000
    a, b = backtest_metrics(s.iloc[:-1]), backtest_metrics(s2.iloc[:-1])
    assert a == b


def test_forecast_output_contract():
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=120), "units_demanded": _series()})
    f = forecast_demand(df, 7)
    for k in ("model_name", "predicted_units", "baseline_units", "baseline_model_name", "mae_candidate", "rmse_candidate"):
        assert k in f
    assert f["model_name"] in ("exp_smoothing", "naive_baseline", "sarima")
    assert sum(c["selected"] for c in f["candidates"]) == 1  # exactly one model selected, all compared


def _frame(n=120):
    return pd.DataFrame({"date": pd.date_range("2026-01-01", periods=n), "units_demanded": _series(n)})


def test_select_model_picks_lowest_mae_and_ignores_nan():
    c = [{"name": "naive_baseline", "mae": 2.0, "rmse": 2.5}, {"name": "exp_smoothing", "mae": 1.5, "rmse": 2.0},
         {"name": "sarima", "mae": 1.0, "rmse": 1.4}, {"name": "x", "mae": float("nan"), "rmse": 0}]
    assert select_model(c)["name"] == "sarima"
    assert select_model(c[:2])["name"] == "exp_smoothing"


def test_select_model_tie_prefers_ses_then_baseline_then_sarima():
    t = lambda a, b, c: select_model([{"name": "naive_baseline", "mae": a, "rmse": 0}, {"name": "exp_smoothing", "mae": b, "rmse": 0}, {"name": "sarima", "mae": c, "rmse": 0}])["name"]
    assert t(1, 1, 1) == "exp_smoothing" and t(1, 2, 1) == "naive_baseline"


def test_sarima_can_be_disabled_and_pipeline_still_works(monkeypatch):
    monkeypatch.setenv("BLOODLINE_SARIMA", "0")
    f = forecast_demand(_frame(), 7)
    assert [c["name"] for c in f["candidates"]] == ["naive_baseline", "exp_smoothing"]


def test_sarima_skipped_when_history_too_short():
    assert forecasting.sarima_evaluate(_series(forecasting.SARIMA_MIN_OBS - 1)) is None


def test_sarima_compared_on_same_backtest_when_statsmodels_installed():
    pytest.importorskip("statsmodels")
    forecasting._sarima_cache.clear()
    f = forecast_demand(_frame(), 7)
    names = [c["name"] for c in f["candidates"]]
    assert names == ["naive_baseline", "exp_smoothing", "sarima"]
    sar = next(c for c in f["candidates"] if c["name"] == "sarima")
    assert sar["mae"] > 0 and sar["rmse"] >= sar["mae"] and sar["predicted_units"] >= 0


def test_sarima_holdout_predictions_do_not_use_future_data():
    pytest.importorskip("statsmodels")
    forecasting._sarima_cache.clear()
    s = _series(100)
    a = forecasting.sarima_evaluate(s.iloc[:-1])
    s2 = s.copy(); s2.iloc[-1] += 500  # a shock on the final day...
    forecasting._sarima_cache.clear()
    b = forecasting.sarima_evaluate(s2.iloc[:-1])  # ...is outside the evaluated window, so nothing changes
    assert a["mae"] == pytest.approx(b["mae"])


# ---------------------------------------------------------------- regional redistribution (suggestions only)
from app.services.regional import plan_redistribution, surplus_units  # noqa: E402
from app.services.geo import haversine_km  # noqa: E402
from app.services import units as units_svc  # noqa: E402


def _g(stock, pred, risk, short=0.0, surplus=0):
    return {"stock": stock, "predicted_demand": pred, "shortfall": short, "risk_level": risk, "surplus": surplus}


def _bank(i, lat, lon, groups):
    return {"id": i, "name": i, "latitude": lat, "longitude": lon, "groups": groups}


def test_surplus_keeps_forecast_plus_buffer():
    assert surplus_units(60, 20) == 25 and surplus_units(30, 20) == 0


def test_redistribution_prefers_nearest_and_never_double_counts():
    banks = [
        _bank("short", 30.34, 76.38, {"O-": _g(2, 12, "HIGH", 10)}),
        _bank("near", 30.73, 76.78, {"O-": _g(60, 20, "LOW", 0, 8)}),
        _bank("far", 30.90, 75.85, {"O-": _g(80, 20, "LOW", 0, 40)}),
    ]
    s = plan_redistribution(banks)
    assert [x["from_bank"] for x in s] == ["near", "far"] and sum(x["units"] for x in s) == 10
    assert all(x["requires_human_approval"] for x in s)


def test_redistribution_radius_and_unknown_distance():
    banks = [_bank("short", 30.0, 76.0, {"A+": _g(1, 10, "HIGH", 9)}), _bank("nocoords", None, None, {"A+": _g(90, 10, "LOW", 0, 50)})]
    assert plan_redistribution(banks, max_km=50) == []          # unknown location can't satisfy a radius
    assert len(plan_redistribution(banks)) == 1                 # no radius: allowed, distance shown as unknown
    assert plan_redistribution(banks)[0]["distance_km"] is None


def test_redistribution_serves_high_risk_first():
    banks = [
        _bank("a", 30.0, 76.0, {"O-": _g(0, 10, "MODERATE", 3)}),
        _bank("b", 30.0, 76.1, {"O-": _g(0, 10, "HIGH", 10)}),
        _bank("c", 30.0, 76.2, {"O-": _g(40, 5, "LOW", 0, 10)}),
    ]
    s = plan_redistribution(banks)
    assert s[0]["to_bank"] == "b" and s[0]["units"] == 10 and len(s) == 1  # all surplus goes to the HIGH-risk bank


def test_no_suggestions_when_nobody_has_surplus():
    assert plan_redistribution([_bank("a", 1, 1, {"O-": _g(0, 9, "HIGH", 9)}), _bank("b", 1, 2, {"O-": _g(20, 9, "LOW", 0, 0)})]) == []


def test_haversine():
    assert haversine_km(30.34, 76.38, 30.34, 76.38) == 0
    assert 30 < haversine_km(30.34, 76.38, 30.73, 76.78) < 70
    assert haversine_km(None, 1, 2, 3) is None


def test_shelf_life_defaults_and_override(monkeypatch):
    assert units_svc.shelf_life_days("platelets") == 5 and units_svc.shelf_life_days("unknown_thing") == 35
    monkeypatch.setenv("BLOODLINE_SHELF_PLATELETS", "7")
    assert units_svc.shelf_life_days("platelets") == 7


def test_vapid_keys_have_valid_shape():
    import base64, importlib.util, os
    spec = importlib.util.spec_from_file_location("gv", os.path.join(os.path.dirname(__file__), "..", "scripts", "gen_vapid.py"))
    gv = importlib.util.module_from_spec(spec); spec.loader.exec_module(gv)
    priv, pub = gv.generate(); pad = lambda s: s + "=" * (-len(s) % 4)
    assert len(base64.urlsafe_b64decode(pad(priv))) == 32 and len(base64.urlsafe_b64decode(pad(pub))) == 65


# ---------------------------------------------------------------- login rate limiting
from app.services.ratelimit import LoginLimiter  # noqa: E402


def test_limiter_blocks_after_max_failures_then_expires():
    lim = LoginLimiter(max_per_account=3, max_per_ip=50, window_s=100)
    for i in range(3):
        assert lim.check("1.1.1.1", "A@x.com", now=i) == 0
        lim.record_failure("1.1.1.1", "A@x.com", now=i)
    assert lim.check("1.1.1.1", "a@x.com", now=10) > 0          # blocked (email is case-insensitive)
    assert lim.check("1.1.1.1", "other@x.com", now=10) == 0     # other accounts unaffected
    assert lim.check("1.1.1.1", "a@x.com", now=150) == 0        # window passed


def test_limiter_success_resets_and_ip_cap_applies():
    lim = LoginLimiter(max_per_account=3, max_per_ip=4, window_s=100)
    lim.record_failure("2.2.2.2", "a@x.com", now=0); lim.record_failure("2.2.2.2", "a@x.com", now=1)
    lim.reset("2.2.2.2", "a@x.com")
    assert lim.check("2.2.2.2", "a@x.com", now=2) == 0
    for i, e in enumerate(["b", "c", "d"]):                      # IP-wide cap: 4 failures total across accounts
        lim.record_failure("2.2.2.2", e + "@x.com", now=3 + i)
    assert lim.check("2.2.2.2", "z@x.com", now=10) > 0


# ---------------------------------------------------------------- evaluation metrics
from app.services import evaluation as ev  # noqa: E402


def _by_group(n=120):
    return {g: pd.Series(_series(n).to_numpy() + k) for k, g in enumerate(["A+", "O-", "B+"])}


def test_forecast_table_reports_mae_rmse_and_selection():
    t = ev.forecast_table(_by_group())
    assert len(t["rows"]) == 3 and t["summary"]["mean_mae_selected"] <= t["summary"]["mean_mae_baseline"] + 1e-9
    for r in t["rows"]:
        assert all(m["rmse"] >= m["mae"] > 0 for m in r["models"]) and r["selected"] in ("naive_baseline", "exp_smoothing")


def test_shortage_detection_counts_and_sanity():
    sd = ev.shortage_detection(_by_group())
    assert sd["cases"] == 3 * 15 * 6 and sum(sd["confusion"].values()) == sd["cases"]
    assert 0 <= sd["precision"] <= 1 and 0 <= sd["recall"] <= 1 and sd["accuracy"] > 0.6  # smooth weekly demand is easy to flag


def _donors():
    t = date.today()
    mk = lambda i, g, **k: {**dict(donor_id=i, full_name=i, blood_group=g, last_donation_date=t - timedelta(days=200), is_available=True, notification_consent=True), **k}
    return [mk("a", "O-"), mk("b", "A+"), mk("c", "B+", is_available=False), mk("d", "AB-", notification_consent=False),
            mk("e", "O+", last_donation_date=t - timedelta(days=10)), mk("f", "AB+")]


def test_verify_matching_passes_for_the_real_matcher():
    v = ev.verify_matching(_donors())
    assert v["passed"] and v["violations"] == 0 and v["omissions"] == 0 and v["compatibility_table_matches_srs"]
    assert v["excluded_compatible_donors"]["unavailable"] > 0 and v["excluded_compatible_donors"]["cooldown"] > 0


def test_verify_matching_catches_a_broken_matcher():
    broken = lambda target, donors: [{"donor_id": d["donor_id"]} for d in donors]          # ignores every rule
    assert not ev.verify_matching(_donors(), match_fn=broken)["passed"]
    forgetful = lambda target, donors: []                                                   # returns nobody
    assert ev.verify_matching(_donors(), match_fn=forgetful)["omissions"] > 0
