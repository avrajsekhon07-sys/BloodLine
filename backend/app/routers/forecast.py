import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db
from ..services.forecasting import forecast_demand

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("/{blood_bank_id}/{blood_group}", response_model=schemas.ForecastOut)
def get_forecast(
    blood_bank_id: str,
    blood_group: str,
    horizon_days: int = 7,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("blood_bank_manager", "system_admin")),
):
    rows = (
        db.query(models.DemandHistory)
        .filter(
            models.DemandHistory.blood_bank_id == blood_bank_id,
            models.DemandHistory.blood_group == blood_group,
        )
        .order_by(models.DemandHistory.date)
        .all()
    )
    if len(rows) < 20:
        raise HTTPException(400, "Not enough demand history to forecast (need at least 20 days). Run the seed script.")

    df = pd.DataFrame([{"date": r.date, "units_demanded": r.units_demanded} for r in rows])
    result = forecast_demand(df, horizon_days=horizon_days)

    # persist the prediction so it's auditable
    pred = models.Prediction(
        blood_bank_id=blood_bank_id,
        blood_group=blood_group,
        model_name=result["model_name"],
        horizon_days=horizon_days,
        predicted_units=result["predicted_units"],
        baseline_units=result["baseline_units"],
        mae_vs_baseline=result.get("mae_candidate"),
    )
    db.add(pred)
    db.commit()

    return schemas.ForecastOut(
        blood_group=blood_group,
        model_name=result["model_name"],
        horizon_days=horizon_days,
        predicted_units=result["predicted_units"],
        baseline_units=result["baseline_units"],
        baseline_model_name=result["baseline_model_name"],
        improvement_over_baseline_pct=result["improvement_over_baseline_pct"],
    )
