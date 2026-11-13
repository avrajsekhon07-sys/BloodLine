"""Unit expiry tracking endpoints (FR-INV-6)."""
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, auth, audit
from ..database import get_db

router = APIRouter(prefix="/units", tags=["units"])
VIEW = ("inventory_staff", "blood_bank_manager", "system_admin", "medical_staff")


@router.get("/expiring")
def expiring_units(
    blood_bank_id: Optional[str] = None,
    days: int = Query(7, ge=0, le=60),
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*VIEW)),
):
    """Tracked units that are overdue or expire within `days`, grouped by blood group and component."""
    today = date.today()
    q = (
        db.query(models.BloodUnit, models.Inventory)
        .join(models.Inventory, models.BloodUnit.inventory_id == models.Inventory.id)
        .filter(models.BloodUnit.status == "available", models.BloodUnit.expiry_date <= today + timedelta(days=days))
    )
    if blood_bank_id:
        q = q.filter(models.Inventory.blood_bank_id == blood_bank_id)
    groups = defaultdict(lambda: {"units": 0, "overdue": 0, "earliest_expiry": None})
    for unit, inv in q.all():
        g = groups[(inv.blood_group.value, inv.component)]
        g["units"] += 1
        g["overdue"] += 1 if unit.expiry_date < today else 0
        if g["earliest_expiry"] is None or unit.expiry_date < g["earliest_expiry"]:
            g["earliest_expiry"] = unit.expiry_date
    rows = [
        {"blood_group": bg, "component": comp, "units": g["units"], "overdue": g["overdue"],
         "earliest_expiry": g["earliest_expiry"].isoformat(), "days_left": (g["earliest_expiry"] - today).days}
        for (bg, comp), g in groups.items()
    ]
    return sorted(rows, key=lambda r: r["days_left"])


@router.post("/expire-overdue")
def expire_overdue(
    blood_bank_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("inventory_staff", "system_admin")),
):
    """Staff-triggered: removes units past their expiry date from stock and logs an 'expiry' transaction."""
    q = (
        db.query(models.BloodUnit, models.Inventory)
        .join(models.Inventory, models.BloodUnit.inventory_id == models.Inventory.id)
        .filter(models.BloodUnit.status == "available", models.BloodUnit.expiry_date < date.today())
    )
    if blood_bank_id:
        q = q.filter(models.Inventory.blood_bank_id == blood_bank_id)
    per_inv = defaultdict(list)
    invs = {}
    for unit, inv in q.all():
        per_inv[inv.id].append(unit)
        invs[inv.id] = inv
    total = 0
    for inv_id, units in per_inv.items():
        inv = invs[inv_id]
        n = min(len(units), inv.quantity_units)
        for u in units:
            u.status = "expired"
        inv.quantity_units -= n
        db.add(models.InventoryTransaction(
            inventory_id=inv.id, txn_type="expiry", quantity_units=len(units),
            note="Units past expiry date removed from stock by staff action",
        ))
        total += len(units)
    if total == 0:
        raise HTTPException(400, "No tracked units are past their expiry date.")
    audit.log(db, user.id, "units_expired", f"{total} unit(s) removed")
    db.commit()
    return {"expired_units": total}
