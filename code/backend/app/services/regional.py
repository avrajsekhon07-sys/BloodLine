"""Regional blood availability: per-bank risk grid and redistribution SUGGESTIONS.

BloodLine never moves blood between banks. Suggestions are recommendations for
authorised staff, who decide and carry out any transfer outside this system."""
import math

from .geo import haversine_km

LOW_STOCK_BUFFER = 15  # a bank keeps this many units (plus its forecast demand) before it counts as having surplus
RISK_ORDER = {"HIGH": 0, "MODERATE": 1, "LOW": 2}


def surplus_units(stock: float, predicted: float) -> int:
    return max(0, int(math.floor(stock - predicted - LOW_STOCK_BUFFER)))


def plan_redistribution(banks: list, max_km: float = None) -> list:
    """banks: [{id, name, latitude, longitude, groups: {bg: {stock, predicted_demand, shortfall, surplus, risk_level}}}]
    Returns suggestions, most urgent first. A bank's surplus is never offered twice."""
    surplus = {(b["id"], bg): g["surplus"] for b in banks for bg, g in b["groups"].items()}
    needs = [
        (b, bg, g) for b in banks for bg, g in b["groups"].items()
        if g["risk_level"] in ("MODERATE", "HIGH") and g["shortfall"] > 0
    ]
    needs.sort(key=lambda t: (RISK_ORDER[t[2]["risk_level"]], -t[2]["shortfall"]))
    out = []
    for b, bg, g in needs:
        remaining = math.ceil(g["shortfall"])
        options = []
        for o in banks:
            if o["id"] == b["id"] or surplus.get((o["id"], bg), 0) <= 0:
                continue
            d = haversine_km(b["latitude"], b["longitude"], o["latitude"], o["longitude"])
            if max_km is not None and (d is None or d > max_km):
                continue
            options.append((d if d is not None else float("inf"), o))
        options.sort(key=lambda t: t[0])
        for d, o in options:
            if remaining <= 0:
                break
            units = min(remaining, surplus[(o["id"], bg)])
            if units <= 0:
                continue
            surplus[(o["id"], bg)] -= units
            remaining -= units
            out.append({
                "blood_group": bg, "units": units, "risk_level_at_receiver": g["risk_level"],
                "from_bank_id": o["id"], "from_bank": o["name"], "to_bank_id": b["id"], "to_bank": b["name"],
                "distance_km": None if d == float("inf") else d,
                "reason": f"{b['name']} is forecast {g['shortfall']:.0f} unit(s) short of {bg}; "
                          f"{o['name']} holds {units} more than its own forecast needs plus a {LOW_STOCK_BUFFER}-unit buffer.",
                "requires_human_approval": True,
            })
    return out
