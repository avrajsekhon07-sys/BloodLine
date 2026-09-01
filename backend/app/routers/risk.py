from typing import List
import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db
from ..services.forecasting import forecast_demand
from ..services.risk import assess_risk

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/{blood_bank_id}", response_model=List[schemas.RiskOut])
def get_risk_overview(
    blood_bank_id: str,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("blood_bank_manager", "system_admin")),
):
    """Runs the forecast + risk rule for every blood group stocked at this bank."""
    inventory_rows = db.query(models.Inventory).filter(models.Inventory.blood_bank_id == blood_bank_id).all()
    results = []

    for inv in inventory_rows:
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

        df = pd.DataFrame([{"date": r.date, "units_demanded": r.units_demanded} for r in demand_rows])
        forecast = forecast_demand(df, horizon_days=7)
        risk = assess_risk(inv.quantity_units, forecast["predicted_units"])

        if risk["risk_level"] in ("MODERATE", "HIGH"):
            db.add(models.Alert(
                blood_bank_id=blood_bank_id,
                blood_group=inv.blood_group,
                risk_level=risk["risk_level"],
                current_stock=risk["current_stock"],
                predicted_demand=risk["predicted_demand"],
                shortfall=risk["shortfall"],
                explanation=risk["explanation"],
            ))

        results.append(schemas.RiskOut(
            blood_bank_id=blood_bank_id,
            blood_group=inv.blood_group.value if hasattr(inv.blood_group, "value") else inv.blood_group,
            **risk,
        ))

    db.commit()
    results.sort(key=lambda r: {"HIGH": 0, "MODERATE": 1, "LOW": 2}[r.risk_level])
    return results
