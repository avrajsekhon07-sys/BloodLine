from datetime import date
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db
from ..services.donor_matching import DONATION_COOLDOWN_DAYS, days_since

router = APIRouter(prefix="/screening", tags=["screening"])

SCREENING_ROLES = ["medical_staff", "blood_bank_manager", "system_admin"]


def _resolve_staff(db: Session, user: models.UserAccount) -> models.Staff:
    staff = db.query(models.Staff).filter(models.Staff.user_id == user.id).first()
    if staff is None:
        raise HTTPException(400, "This account has no staff profile linked to a blood bank.")
    return staff


@router.get("/candidates", response_model=List[schemas.ScreeningCandidateOut])
def list_candidates(
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*SCREENING_ROLES)),
):
    """
    Donors who are available, consented, and past the donation cooldown —
    i.e. worth screening next. This does not decide eligibility; it's a
    worklist for medical staff, same principle as donor matching.
    """
    donors = db.query(models.Donor).all()
    out = []
    for d in donors:
        gap = days_since(d.last_donation_date)
        cooldown_cleared = gap >= DONATION_COOLDOWN_DAYS
        last_record = (
            db.query(models.ScreeningRecord)
            .filter(models.ScreeningRecord.donor_id == d.id)
            .order_by(models.ScreeningRecord.recorded_at.desc())
            .first()
        )
        out.append(schemas.ScreeningCandidateOut(
            donor_id=d.id,
            full_name=d.user.full_name,
            blood_group=d.blood_group.value if hasattr(d.blood_group, "value") else d.blood_group,
            days_since_last_donation=None if d.last_donation_date is None else gap,
            cooldown_cleared=cooldown_cleared,
            is_available=d.is_available,
            notification_consent=d.notification_consent,
            last_screening_outcome=last_record.outcome if last_record else None,
            last_screened_at=last_record.recorded_at if last_record else None,
        ))
    return out


@router.post("", response_model=schemas.ScreeningRecordOut)
def record_screening(
    payload: schemas.ScreeningRecordCreate,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("medical_staff", "system_admin")),
):
    if payload.outcome not in ("eligible", "deferred", "rejected"):
        raise HTTPException(400, "outcome must be one of: eligible, deferred, rejected")

    donor = db.query(models.Donor).filter(models.Donor.id == payload.donor_id).first()
    if donor is None:
        raise HTTPException(404, "Donor not found")

    staff = _resolve_staff(db, user)

    record = models.ScreeningRecord(
        donor_id=donor.id,
        performed_by_id=staff.id,
        outcome=payload.outcome,
        notes=payload.notes,
    )
    db.add(record)

    # An "eligible" screening outcome updates the donor's own status so the
    # donor dashboard reflects it — donation itself still happens separately.
    if payload.outcome == "eligible":
        donor.last_donation_date = date.today()

    db.commit()
    db.refresh(record)

    return schemas.ScreeningRecordOut(
        id=record.id,
        donor_id=donor.id,
        donor_name=donor.user.full_name,
        donor_blood_group=donor.blood_group.value if hasattr(donor.blood_group, "value") else donor.blood_group,
        performed_by_name=staff.user.full_name,
        outcome=record.outcome,
        notes=record.notes,
        recorded_at=record.recorded_at,
    )


@router.get("/donor/{donor_id}", response_model=List[schemas.ScreeningRecordOut])
def get_donor_screening_history(
    donor_id: str,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*SCREENING_ROLES)),
):
    donor = db.query(models.Donor).filter(models.Donor.id == donor_id).first()
    if donor is None:
        raise HTTPException(404, "Donor not found")

    records = (
        db.query(models.ScreeningRecord)
        .filter(models.ScreeningRecord.donor_id == donor_id)
        .order_by(models.ScreeningRecord.recorded_at.desc())
        .all()
    )
    return [
        schemas.ScreeningRecordOut(
            id=r.id,
            donor_id=donor.id,
            donor_name=donor.user.full_name,
            donor_blood_group=donor.blood_group.value if hasattr(donor.blood_group, "value") else donor.blood_group,
            performed_by_name=r.performed_by.user.full_name,
            outcome=r.outcome,
            notes=r.notes,
            recorded_at=r.recorded_at,
        )
        for r in records
    ]
