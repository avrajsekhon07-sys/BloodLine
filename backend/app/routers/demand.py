from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/demand", tags=["demand"])


@router.get("/history", response_model=List[schemas.DemandPoint])
def get_demand_history(
    blood_group: str,
    blood_bank_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("blood_bank_manager", "inventory_staff", "system_admin")),
):
    """
    Returns the stored synthetic/simulated demand history for one blood
    group — the same DemandHistory rows the forecasting pipeline reads.

    blood_bank_id is optional: the W5 prototype seeds a single blood bank,
    so if it's omitted we resolve it automatically. Existing callers that
    already pass blood_bank_id explicitly are unaffected.
    """
    if blood_bank_id is None:
        bank = db.query(models.BloodBank).first()
        if bank is None:
            raise HTTPException(400, "No blood bank found — run the seed script first.")
        blood_bank_id = bank.id

    rows = (
        db.query(models.DemandHistory)
        .filter(
            models.DemandHistory.blood_bank_id == blood_bank_id,
            models.DemandHistory.blood_group == blood_group,
        )
        .order_by(models.DemandHistory.date)
        .all()
    )
    return rows
