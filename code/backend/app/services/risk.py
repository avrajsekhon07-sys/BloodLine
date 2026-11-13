"""
Shortage-risk detection.

Deliberately a transparent rule layer on top of the forecast, not a
black-box classifier — the manager needs to be able to see exactly why a
blood group was flagged.

    shortfall = predicted_demand - current_stock

    shortfall <= 0                       -> LOW    (stock covers forecast)
    0 < shortfall <= 0.25 * current_stock -> MODERATE
    shortfall > 0.25 * current_stock      -> HIGH
    (current_stock == 0 and predicted_demand > 0) -> HIGH, forced

This mirrors the worked example in the proposal: 20 units in stock vs 25
predicted demand -> shortfall 5 -> flagged.
"""
from typing import Dict


def assess_risk(current_stock: int, predicted_demand: float) -> Dict:
    shortfall = round(predicted_demand - current_stock, 1)

    if current_stock == 0 and predicted_demand > 0:
        level = "HIGH"
    elif shortfall <= 0:
        level = "LOW"
    elif shortfall <= 0.25 * max(current_stock, 1):
        level = "MODERATE"
    else:
        level = "HIGH"

    explanation = (
        f"Current stock is {current_stock} units. Forecasted near-term demand is "
        f"{predicted_demand} units, a shortfall of {max(shortfall, 0)} units. "
        f"Classified {level} because "
        + (
            "stock is fully depleted while demand is expected."
            if current_stock == 0 and predicted_demand > 0
            else "the shortfall is non-positive (stock covers forecast)."
            if level == "LOW"
            else "the shortfall is at or below 25% of current stock."
            if level == "MODERATE"
            else "the shortfall exceeds 25% of current stock."
        )
    )

    return {
        "current_stock": current_stock,
        "predicted_demand": predicted_demand,
        "shortfall": max(shortfall, 0),
        "risk_level": level,
        "explanation": explanation,
    }
