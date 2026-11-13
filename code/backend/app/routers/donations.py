"""Donation recording (FR-INV-5).

Business rule from the SRS: final donor clearance is given only by medical
staff, and a donation is recorded after screening. So a donation is accepted
only if the donor's latest screening outcome is 'eligible' (entered by a
person) and the cooldown has passed. Recording it updates last_donation_date
and increases stock, with a receipt transaction.
"""
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth, audit
from ..services import units as units_svc
from ..database import get_db
from ..services.donor_matching import DONATION_COOLDOWN_DAYS, days_since

router = APIRouter(prefix="/donations", tags=["donations"])

RECORD_ROLES = ["inventory_staff", "medical_staff", "system_admin"]
VIEW_ROLES = RECORD_ROLES + ["blood_bank_manager"]


def _latest_screening(db: Session, donor_id: str):
    return (
        db.query(models.ScreeningRecord)
        .filter(models.ScreeningRecord.donor_id == donor_id)
        .order_by(models.ScreeningRecord.recorded_at.desc())
        .first()
    )


def _ready(db: Session, donor: models.Donor):
    """Latest screening is 'eligible', recorded after any previous donation, cooldown cleared."""
    rec = _latest_screening(db, donor.id)
    if rec is None or rec.outcome != "eligible":
        return None
    if donor.last_donation_date and rec.recorded_at.date() < donor.last_donation_date:
        return None
    if days_since(donor.last_donation_date) < DONATION_COOLDOWN_DAYS:
        return None
    return rec


@router.get("/ready-donors", response_model=List[schemas.ReadyDonorOut])
def ready_donors(
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*RECORD_ROLES)),
):
    """Donors whom medical staff have screened as eligible and who can donate now."""
    out = []
    for d in db.query(models.Donor).all():
        rec = _ready(db, d)
        if rec:
            out.append(schemas.ReadyDonorOut(
                donor_id=d.id, full_name=d.user.full_name, blood_group=d.blood_group.value, screened_at=rec.recorded_at,
            ))
    return out


@router.post("", response_model=schemas.DonationRecordedOut, status_code=201)
def record_donation(
    payload: schemas.DonationCreate,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*RECORD_ROLES)),
):
    if not 1 <= payload.units_collected <= 2:
        raise HTTPException(400, "units_collected must be 1 or 2")
    donation_date = payload.donation_date or date.today()
    if donation_date > date.today():
        raise HTTPException(400, "donation_date cannot be in the future")

    donor = db.query(models.Donor).filter(models.Donor.id == payload.donor_id).first()
    if donor is None:
        raise HTTPException(404, "Donor not found")
    if _ready(db, donor) is None:
        raise HTTPException(
            400,
            "A donation can only be recorded after medical staff screen the donor as 'eligible' "
            f"(and the {DONATION_COOLDOWN_DAYS}-day cooldown has passed).",
        )

    bank_id = payload.blood_bank_id
    if bank_id is None:
        staff = user.staff_profile
        bank = db.query(models.BloodBank).filter(models.BloodBank.id == staff.blood_bank_id).first() if staff else db.query(models.BloodBank).first()
        if bank is None:
            raise HTTPException(400, "No blood bank found — run the seed script first.")
        bank_id = bank.id

    donation = models.Donation(
        donor_id=donor.id, blood_bank_id=bank_id, donation_date=donation_date, units_collected=payload.units_collected,
    )
    db.add(donation)
    donor.last_donation_date = donation_date

    inv = (
        db.query(models.Inventory)
        .filter(
            models.Inventory.blood_bank_id == bank_id,
            models.Inventory.blood_group == donor.blood_group,
            models.Inventory.component == "whole_blood",
        )
        .first()
    )
    if inv is None:
        inv = models.Inventory(blood_bank_id=bank_id, blood_group=donor.blood_group, component="whole_blood", quantity_units=0)
        db.add(inv)
        db.flush()
    inv.quantity_units += payload.units_collected
    db.flush()
    units_svc.add_units(db, inv, payload.units_collected, donation_date)
    db.add(models.InventoryTransaction(
        inventory_id=inv.id, txn_type="receipt", quantity_units=payload.units_collected,
        note=f"Donation {donation.id} from {donor.user.full_name}",
    ))
    audit.log(db, user.id, "donation_recorded", f"donor {donor.id}, {payload.units_collected} unit(s) of {donor.blood_group.value}")
    db.commit()
    db.refresh(donation)
    return schemas.DonationRecordedOut(
        id=donation.id, donor_id=donor.id, donor_name=donor.user.full_name, blood_group=donor.blood_group.value,
        units_collected=donation.units_collected, donation_date=donation.donation_date, new_stock=inv.quantity_units,
    )
