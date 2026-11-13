from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db
from ..services.donor_matching import DONATION_COOLDOWN_DAYS, days_since

router = APIRouter(prefix="/donor", tags=["donor"])


def _resolve_donor(db: Session, user: models.UserAccount) -> models.Donor:
    donor = db.query(models.Donor).filter(models.Donor.user_id == user.id).first()
    if donor is None:
        raise HTTPException(400, "This account has no donor profile.")
    return donor


@router.get("/me", response_model=schemas.DonorProfileOut)
def get_my_profile(
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("donor")),
):
    donor = _resolve_donor(db, user)
    gap = days_since(donor.last_donation_date)
    donations = (
        db.query(models.Donation)
        .filter(models.Donation.donor_id == donor.id)
        .order_by(models.Donation.donation_date.desc())
        .all()
    )
    return schemas.DonorProfileOut(
        donor_id=donor.id,
        full_name=user.full_name,
        email=user.email,
        blood_group=donor.blood_group.value if hasattr(donor.blood_group, "value") else donor.blood_group,
        is_available=donor.is_available,
        notification_consent=donor.notification_consent,
        last_donation_date=donor.last_donation_date,
        days_since_last_donation=None if donor.last_donation_date is None else gap,
        cooldown_cleared=gap >= DONATION_COOLDOWN_DAYS,
        donations=[
            schemas.DonationOut(id=d.id, donation_date=d.donation_date, units_collected=d.units_collected)
            for d in donations
        ],
    )


@router.put("/me/availability", response_model=schemas.DonorProfileOut)
def update_my_availability(
    payload: schemas.DonorAvailabilityUpdate,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("donor")),
):
    donor = _resolve_donor(db, user)
    donor.is_available = payload.is_available
    donor.notification_consent = payload.notification_consent
    db.commit()
    db.refresh(donor)
    return get_my_profile(db=db, user=user)
