"""
Donor matching.

This module RECOMMENDS candidate donors to authorized staff. It never
makes an actual medical eligibility decision — that stays with Medical/
Screening Staff (see models.ScreeningRecord). Output is a ranked list with
the reasons behind each score, so staff can sanity-check the suggestion.
"""
from datetime import date
from typing import List, Dict

DONATION_COOLDOWN_DAYS = 90

# Standard whole-blood donor -> recipient compatibility (who CAN donate TO a
# patient of the given blood_group). Kept simple for the prototype; the
# real system may narrow this per component (RBC/plasma/platelets differ).
COMPATIBLE_DONORS = {
    "O-":  ["O-"],
    "O+":  ["O-", "O+"],
    "A-":  ["O-", "A-"],
    "A+":  ["O-", "O+", "A-", "A+"],
    "B-":  ["O-", "B-"],
    "B+":  ["O-", "O+", "B-", "B+"],
    "AB-": ["O-", "A-", "B-", "AB-"],
    "AB+": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
}


def days_since(d) -> int:
    if d is None:
        return 999
    return (date.today() - d).days


def match_donors(target_blood_group: str, donors: List[Dict]) -> List[Dict]:
    """
    donors: list of dicts with keys donor_id, full_name, blood_group,
    last_donation_date (date|None), is_available, notification_consent.

    Returns a ranked list of eligible-to-contact candidates (donor.
    availability and consent are always respected — staff still perform
    final medical screening before any donation).
    """
    eligible_groups = COMPATIBLE_DONORS.get(target_blood_group, [])
    results = []

    for d in donors:
        if d["blood_group"] not in eligible_groups:
            continue
        if not d.get("is_available", False):
            continue
        if not d.get("notification_consent", False):
            continue

        gap = days_since(d.get("last_donation_date"))
        if gap < DONATION_COOLDOWN_DAYS:
            continue  # not medically eligible by cooldown; excluded, not just deprioritized

        reasons = [f"Compatible donor for {target_blood_group} recipients"]
        score = 50.0

        if d["blood_group"] == target_blood_group:
            score += 20
            reasons.append("Exact blood-group match")
        if gap >= 180:
            score += 15
            reasons.append(f"{gap} days since last donation (well past cooldown)")
        else:
            reasons.append(f"{gap} days since last donation (cooldown cleared)")

        results.append({
            "donor_id": d["donor_id"],
            "full_name": d["full_name"],
            "blood_group": d["blood_group"],
            "days_since_last_donation": None if d.get("last_donation_date") is None else gap,
            "is_available": d["is_available"],
            "notification_consent": d["notification_consent"],
            "match_score": round(score, 1),
            "reasons": reasons,
        })

    results.sort(key=lambda r: r["match_score"], reverse=True)
    return results
