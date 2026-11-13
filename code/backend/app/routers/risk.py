from datetime import datetime, timedelta
from typing import List, Optional
import pandas as pd
from fastapi import APIRouter, Depends, Query
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

        recent = (
            db.query(models.Alert)
            .filter(
                models.Alert.blood_bank_id == blood_bank_id,
                models.Alert.blood_group == inv.blood_group,
                models.Alert.risk_level == risk["risk_level"],
                models.Alert.current_stock == risk["current_stock"],
                models.Alert.created_at >= datetime.utcnow() - timedelta(hours=1),
            )
            .first()
        )
        if risk["risk_level"] in ("MODERATE", "HIGH") and recent is None:
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


@router.get("/{blood_bank_id}/history", response_model=List[schemas.AlertHistoryOut])
def get_risk_history(
    blood_bank_id: str,
    blood_group: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("blood_bank_manager", "system_admin")),
):
    """Stored MODERATE/HIGH alerts over time (FR-RISK-3) for historical risk trends."""
    q = db.query(models.Alert).filter(
        models.Alert.blood_bank_id == blood_bank_id,
        models.Alert.created_at >= datetime.utcnow() - timedelta(days=days),
    )
    if blood_group:
        q = q.filter(models.Alert.blood_group == blood_group)
    return [
        schemas.AlertHistoryOut(
            created_at=a.created_at,
            blood_group=a.blood_group.value,
            risk_level=a.risk_level.value,
            current_stock=a.current_stock,
            predicted_demand=a.predicted_demand,
            shortfall=a.shortfall,
        )
        for a in q.order_by(models.Alert.created_at.desc()).limit(500).all()
    ]
