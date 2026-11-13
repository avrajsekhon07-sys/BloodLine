"""Regional blood availability across blood banks (FR-REG-1).
Redistribution output is SUGGESTIONS ONLY: authorised staff decide and perform any transfer."""
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, auth
from ..database import get_db
from ..services.forecasting import forecast_demand
from ..services.regional import plan_redistribution, surplus_units
from ..services.risk import assess_risk

router = APIRouter(prefix="/regional", tags=["regional"])
STAFF = ("blood_bank_manager", "system_admin", "inventory_staff", "medical_staff")
MANAGERS = ("blood_bank_manager", "system_admin")


def _bank_view(db: Session, bank: models.BloodBank) -> dict:
    stock = {}
    for inv in db.query(models.Inventory).filter(models.Inventory.blood_bank_id == bank.id).all():
        stock[inv.blood_group.value] = stock.get(inv.blood_group.value, 0) + inv.quantity_units
    groups = {}
    for bg, qty in stock.items():
        rows = (
            db.query(models.DemandHistory)
            .filter(models.DemandHistory.blood_bank_id == bank.id, models.DemandHistory.blood_group == bg)
            .order_by(models.DemandHistory.date).all()
        )
        if len(rows) < 20:
            continue
        df = pd.DataFrame([{"date": r.date, "units_demanded": r.units_demanded} for r in rows])
        fc = forecast_demand(df, 7, use_sarima=False)  # fast path: SARIMA is reserved for the single-bank pages
        risk = assess_risk(qty, fc["predicted_units"])
        groups[bg] = {
            "stock": qty, "predicted_demand": risk["predicted_demand"], "shortfall": risk["shortfall"],
            "risk_level": risk["risk_level"], "surplus": surplus_units(qty, risk["predicted_demand"]),
            "explanation": risk["explanation"],
        }
    return {"id": bank.id, "name": bank.name, "address": bank.address, "latitude": bank.latitude,
            "longitude": bank.longitude, "groups": groups}


@router.get("/banks")
def list_banks(db: Session = Depends(get_db), user: models.UserAccount = Depends(auth.require_roles(*STAFF))):
    return [{"id": b.id, "name": b.name, "address": b.address, "latitude": b.latitude, "longitude": b.longitude}
            for b in db.query(models.BloodBank).order_by(models.BloodBank.name).all()]


@router.get("/overview")
def regional_overview(db: Session = Depends(get_db), user: models.UserAccount = Depends(auth.require_roles(*MANAGERS))):
    banks = [_bank_view(db, b) for b in db.query(models.BloodBank).order_by(models.BloodBank.name).all()]
    for b in banks:
        levels = [g["risk_level"] for g in b["groups"].values()]
        b["worst_risk"] = "HIGH" if "HIGH" in levels else "MODERATE" if "MODERATE" in levels else "LOW" if levels else None
    return {"banks": banks}


@router.get("/redistribution")
def redistribution_suggestions(
    max_distance_km: Optional[float] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*MANAGERS)),
):
    banks = [_bank_view(db, b) for b in db.query(models.BloodBank).all()]
    return {
        "note": "Suggestions only. BloodLine does not move blood; authorised blood-centre staff must approve and carry out any transfer.",
        "suggestions": plan_redistribution(banks, max_distance_km),
    }
