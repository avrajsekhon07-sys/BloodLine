import pandas as pd
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db
from ..services.forecasting import forecast_demand
from ..services.risk import assess_risk

router = APIRouter(prefix="/reports", tags=["reports"])

MANAGER_ROLES = ["blood_bank_manager", "system_admin"]


@router.get("/summary", response_model=schemas.ReportsSummaryOut)
def reports_summary(
    blood_bank_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*MANAGER_ROLES)),
):
    if blood_bank_id is None:
        bank = db.query(models.BloodBank).first()
        if bank is None:
            raise HTTPException(400, "No blood bank found — run the seed script first.")
        blood_bank_id = bank.id

    inventory_rows = db.query(models.Inventory).filter(models.Inventory.blood_bank_id == blood_bank_id).all()
    total_inventory = sum(i.quantity_units for i in inventory_rows)

    inv_ids = [i.id for i in inventory_rows]
    txns = db.query(models.InventoryTransaction).filter(models.InventoryTransaction.inventory_id.in_(inv_ids)).all() if inv_ids else []
    units_received = sum(t.quantity_units for t in txns if t.txn_type == "receipt")
    units_issued = sum(t.quantity_units for t in txns if t.txn_type == "issue")
    units_expired_discarded = sum(t.quantity_units for t in txns if t.txn_type in ("expiry", "discard"))

    high_risk, moderate_risk = [], []
    demand_summary, forecast_summary = {}, {}
    inventory_by_group = {}

    for inv in inventory_rows:
        bg = inv.blood_group.value if hasattr(inv.blood_group, "value") else inv.blood_group
        inventory_by_group[bg] = inv.quantity_units

        demand_rows = (
            db.query(models.DemandHistory)
            .filter(
                models.DemandHistory.blood_bank_id == blood_bank_id,
                models.DemandHistory.blood_group == inv.blood_group,
            )
            .order_by(models.DemandHistory.date)
            .all()
        )
        if len(demand_rows) < 20:
            continue

        values = [r.units_demanded for r in demand_rows]
        demand_summary[bg] = round(sum(values) / len(values), 1)

        df = pd.DataFrame([{"date": r.date, "units_demanded": r.units_demanded} for r in demand_rows])
        forecast = forecast_demand(df, horizon_days=7)
        forecast_summary[bg] = forecast["predicted_units"]

        risk = assess_risk(inv.quantity_units, forecast["predicted_units"])
        if risk["risk_level"] == "HIGH":
            high_risk.append(bg)
        elif risk["risk_level"] == "MODERATE":
            moderate_risk.append(bg)

    requests_summary = {}
    for status in ("pending", "fulfilled", "rejected", "cancelled"):
        requests_summary[status] = db.query(models.BloodRequest).filter(models.BloodRequest.status == status).count()

    return schemas.ReportsSummaryOut(
        blood_bank_id=blood_bank_id,
        total_inventory_units=total_inventory,
        units_received=units_received,
        units_issued=units_issued,
        units_expired_discarded=units_expired_discarded,
        high_risk_groups=high_risk,
        moderate_risk_groups=moderate_risk,
        demand_summary=demand_summary,
        forecast_summary=forecast_summary,
        inventory_by_group=inventory_by_group,
        requests_summary=requests_summary,
    )
