"""Scenario tools for demos and planning.
* GET  /demo/whatif     read-only: re-run the risk rule with demand scaled by a percentage (nothing is stored)
* POST /demo/scenario   MUTATES stock to simulate a shortage / restock. Demo only: off when BLOODLINE_DEMO_TOOLS=0
                        or BLOODLINE_ENV=production. Recorded in the transaction history and audit log as simulated."""
import os
from collections import defaultdict
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, auth, audit
from ..database import get_db
from ..services import units as units_svc
from ..services.forecasting import forecast_demand
from ..services.risk import assess_risk

router = APIRouter(prefix="/demo", tags=["demo"])
MANAGERS = ("blood_bank_manager", "system_admin")
SHORTAGE_UNITS, RESTOCK_UNITS = 3, 60


def tools_enabled() -> bool:
    return os.getenv("BLOODLINE_DEMO_TOOLS", "1") == "1" and os.getenv("BLOODLINE_ENV") != "production"


def _bank(db, bank_id):
    bank = db.query(models.BloodBank).filter(models.BloodBank.id == bank_id).first() if bank_id else db.query(models.BloodBank).first()
    if bank is None:
        raise HTTPException(404, "Blood bank not found")
    return bank


@router.get("/status")
def status(user: models.UserAccount = Depends(auth.require_roles(*MANAGERS))):
    return {"scenario_tools": tools_enabled()}


@router.get("/whatif")
def what_if(
    blood_bank_id: Optional[str] = None,
    demand_change_pct: float = Query(0, ge=-90, le=300),
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*MANAGERS)),
):
    bank = _bank(db, blood_bank_id)
    stock = defaultdict(int)
    for inv in db.query(models.Inventory).filter(models.Inventory.blood_bank_id == bank.id).all():
        stock[inv.blood_group.value] += inv.quantity_units
    out = []
    for g, qty in stock.items():
        rows = (
            db.query(models.DemandHistory)
            .filter(models.DemandHistory.blood_bank_id == bank.id, models.DemandHistory.blood_group == g)
            .order_by(models.DemandHistory.date).all()
        )
        if len(rows) < 20:
            continue
        df = pd.DataFrame([{"date": r.date, "units_demanded": r.units_demanded} for r in rows])
        base = forecast_demand(df, 7)["predicted_units"]
        scen = round(base * (1 + demand_change_pct / 100), 1)
        risk = assess_risk(qty, scen)
        out.append({
            "blood_group": g, "current_stock": qty, "baseline_predicted": base, "scenario_predicted": scen,
            "shortfall": risk["shortfall"], "risk_level": risk["risk_level"],
            "baseline_risk_level": assess_risk(qty, base)["risk_level"], "explanation": risk["explanation"],
        })
    out.sort(key=lambda r: {"HIGH": 0, "MODERATE": 1, "LOW": 2}[r["risk_level"]])
    return {"demand_change_pct": demand_change_pct, "groups": out, "note": "Read-only what-if. Nothing is saved."}


class ScenarioIn(BaseModel):
    blood_group: str
    action: str  # "shortage" | "restock"
    blood_bank_id: Optional[str] = None


@router.post("/scenario")
def scenario(
    payload: ScenarioIn,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*MANAGERS)),
):
    if not tools_enabled():
        raise HTTPException(404, "Not found")
    if payload.action not in ("shortage", "restock"):
        raise HTTPException(400, "action must be 'shortage' or 'restock'")
    try:
        group = models.BloodGroup(payload.blood_group)
    except ValueError:
        raise HTTPException(400, "Unknown blood_group")
    bank = _bank(db, payload.blood_bank_id)
    inv = (
        db.query(models.Inventory)
        .filter(models.Inventory.blood_bank_id == bank.id, models.Inventory.blood_group == group, models.Inventory.component == "whole_blood")
        .first()
    )
    if inv is None:
        raise HTTPException(404, "No whole-blood inventory row for that group")
    target = SHORTAGE_UNITS if payload.action == "shortage" else RESTOCK_UNITS
    before, delta = inv.quantity_units, target - inv.quantity_units
    if delta != 0:
        inv.quantity_units = target
        if delta < 0:
            units_svc.consume_units(db, inv, -delta, "discarded")
        else:
            units_svc.add_units(db, inv, delta)
        db.add(models.InventoryTransaction(
            inventory_id=inv.id, txn_type="discard" if delta < 0 else "receipt", quantity_units=abs(delta),
            note=f"DEMO scenario ({payload.action}): simulated, not a real stock movement",
        ))
        audit.log(db, user.id, "demo_scenario", f"{payload.action} {group.value}: {before} -> {target} units")
        db.commit()
    return {"blood_group": group.value, "previous_units": before, "new_units": target, "action": payload.action}
