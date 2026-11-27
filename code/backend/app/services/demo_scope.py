"""Database query helpers that keep real and synthetic demo records separate."""
from fastapi import HTTPException

from .. import models


def banks(db, user):
    return db.query(models.BloodBank).filter(models.BloodBank.is_demo.is_(bool(user.is_demo)))


def bank(db, user, bank_id=None):
    query = banks(db, user)
    if bank_id:
        query = query.filter(models.BloodBank.id == bank_id)
    if user.role.name.value in ("inventory_staff", "medical_staff") and user.staff_profile:
        query = query.filter(models.BloodBank.id == user.staff_profile.blood_bank_id)
    result = query.order_by(models.BloodBank.name).first()
    if result is None:
        raise HTTPException(404, "Blood bank not found")
    return result


def inventory(db, user):
    return db.query(models.Inventory).join(models.BloodBank).filter(
        models.BloodBank.is_demo.is_(bool(user.is_demo))
    )


def transactions(db, user):
    return db.query(models.InventoryTransaction).join(models.Inventory).join(models.BloodBank).filter(
        models.BloodBank.is_demo.is_(bool(user.is_demo))
    )


def demand(db, user):
    return db.query(models.DemandHistory).join(models.BloodBank).filter(
        models.BloodBank.is_demo.is_(bool(user.is_demo))
    )


def alerts(db, user):
    return db.query(models.Alert).join(models.BloodBank).filter(
        models.BloodBank.is_demo.is_(bool(user.is_demo))
    )


def donors(db, user):
    return db.query(models.Donor).join(models.UserAccount).filter(
        models.UserAccount.is_demo.is_(bool(user.is_demo))
    )


def requests(db, user):
    return db.query(models.BloodRequest).join(models.Hospital).filter(
        models.Hospital.is_demo.is_(bool(user.is_demo))
    )


def donor(db, user, donor_id):
    result = donors(db, user).filter(models.Donor.id == donor_id).first()
    if result is None:
        raise HTTPException(404, "Donor not found")
    return result


def require_real_admin(user):
    if user.is_demo:
        raise HTTPException(403, "Demo administrator access is read-only.")
