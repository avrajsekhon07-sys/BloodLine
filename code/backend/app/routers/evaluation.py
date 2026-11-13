"""Evaluation report (proposal section 6): forecasting error, shortage-risk performance, matching
and notification-targeting correctness. Response-time measurement is done from the browser, where
the latency is real, on the Evaluation page."""
from collections import defaultdict
from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, auth
from ..database import get_db
from ..services import evaluation as ev

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/report")
def evaluation_report(
    blood_bank_id: Optional[str] = None,
    include_sarima: bool = False,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("blood_bank_manager", "system_admin")),
):
    bank = db.query(models.BloodBank).filter(models.BloodBank.id == blood_bank_id).first() if blood_bank_id else db.query(models.BloodBank).first()
    rows = (
        db.query(models.DemandHistory).filter(models.DemandHistory.blood_bank_id == bank.id)
        .order_by(models.DemandHistory.date).all()
    ) if bank else []
    by = defaultdict(list)
    for r in rows:
        by[getattr(r.blood_group, "value", r.blood_group)].append(r.units_demanded)
    series = {g: pd.Series(v, dtype=float) for g, v in by.items()}

    donors = [
        {"donor_id": d.id, "full_name": d.user.full_name, "blood_group": d.blood_group.value,
         "last_donation_date": d.last_donation_date, "is_available": d.is_available,
         "notification_consent": d.notification_consent}
        for d in db.query(models.Donor).all()
    ]
    notified = db.query(models.DonorNotification).all()
    consent = {d["donor_id"]: d["notification_consent"] for d in donors}
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "bank": {"id": bank.id, "name": bank.name} if bank else None,
        "data_note": "Demand history is synthetic/simulated. These figures evaluate the pipeline, not clinical validity.",
        "forecast": ev.forecast_table(series, include_sarima),
        "shortage_detection": ev.shortage_detection(series),
        "matching": ev.verify_matching(donors),
        "notifications": {
            "sent_total": len(notified),
            "to_donors_without_consent_now": sum(1 for n in notified if not consent.get(n.donor_id, False)),
            "note": "Outreach recipients come from the same rule-checked matching function. A non-zero count means a donor withdrew consent after being notified.",
        },
    }
