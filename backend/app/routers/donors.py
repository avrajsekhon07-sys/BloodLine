from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db
from ..services.donor_matching import match_donors

router = APIRouter(prefix="/donors", tags=["donors"])


@router.get("/match/{blood_group}", response_model=List[schemas.DonorMatchOut])
def get_donor_matches(
    blood_group: str,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("blood_bank_manager", "system_admin")),
):
    """
    Recommends candidate donors for a shortage in `blood_group`. This is a
    recommendation only — final medical eligibility is decided by Medical/
    Screening Staff, never automatically by this endpoint.
    """
    donors = db.query(models.Donor).all()
    donor_dicts = [
        {
            "donor_id": d.id,
            "full_name": d.user.full_name,
            "blood_group": d.blood_group.value if hasattr(d.blood_group, "value") else d.blood_group,
            "last_donation_date": d.last_donation_date,
            "is_available": d.is_available,
            "notification_consent": d.notification_consent,
        }
        for d in donors
    ]
    ranked = match_donors(blood_group, donor_dicts)
    return [schemas.DonorMatchOut(**r) for r in ranked]
