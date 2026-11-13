"""Administrator account management (FR-ADM-1) and the audit log (FR-ADM-2).
The read-only summary and user list live in routers/admin.py."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas, auth, audit
from ..database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])
ADMIN = ("system_admin",)
STAFF_ROLES = {"blood_bank_manager", "inventory_staff", "medical_staff"}


def _out(u: models.UserAccount) -> schemas.AdminUserOut:
    return schemas.AdminUserOut(id=u.id, full_name=u.full_name, email=u.email, role=u.role.name.value, is_active=u.is_active)


def _role(db: Session, name: str) -> models.Role:
    try:
        rn = models.RoleName(name)
    except ValueError:
        raise HTTPException(400, "role must be one of: " + ", ".join(r.value for r in models.RoleName))
    role = db.query(models.Role).filter(models.Role.name == rn).first()
    if role is None:
        raise HTTPException(400, "Roles are not set up — run the seed script first.")
    return role


def _ensure_profile(db: Session, user: models.UserAccount, role_name: str, p):
    """Create the role-specific profile row that the role's workflows depend on."""
    if role_name in STAFF_ROLES and user.staff_profile is None:
        bank = db.query(models.BloodBank).filter(models.BloodBank.id == p.get("blood_bank_id")).first() if p.get("blood_bank_id") else db.query(models.BloodBank).first()
        if bank is None:
            raise HTTPException(400, "No blood bank found for this staff account.")
        db.add(models.Staff(user_id=user.id, blood_bank_id=bank.id, designation=role_name))
    elif role_name == "hospital_coordinator" and user.hospital_user_profile is None:
        h = db.query(models.Hospital).filter(models.Hospital.id == p.get("hospital_id")).first() if p.get("hospital_id") else db.query(models.Hospital).first()
        if h is None:
            raise HTTPException(400, "No hospital found for this coordinator account.")
        db.add(models.HospitalUser(user_id=user.id, hospital_id=h.id))
    elif role_name == "donor" and user.donor_profile is None:
        try:
            bg = models.BloodGroup(p.get("blood_group"))
        except ValueError:
            raise HTTPException(400, "A donor account needs a valid blood_group.")
        db.add(models.Donor(user_id=user.id, blood_group=bg, is_available=True, notification_consent=False))


@router.post("/users", response_model=schemas.AdminUserOut, status_code=201)
def create_user(
    payload: schemas.AdminUserCreate,
    db: Session = Depends(get_db),
    admin: models.UserAccount = Depends(auth.require_roles(*ADMIN)),
):
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.query(models.UserAccount).filter(models.UserAccount.email == payload.email).first():
        raise HTTPException(400, "An account with this email already exists")
    role = _role(db, payload.role)
    user = models.UserAccount(
        email=payload.email, hashed_password=auth.hash_password(payload.password),
        full_name=payload.full_name.strip(), role_id=role.id,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    _ensure_profile(db, user, payload.role, payload.model_dump())
    audit.log(db, admin.id, "user_created", f"{payload.email} as {payload.role}")
    db.commit()
    db.refresh(user)
    return _out(user)


@router.patch("/users/{user_id}", response_model=schemas.AdminUserOut)
def update_user(
    user_id: str,
    payload: schemas.AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: models.UserAccount = Depends(auth.require_roles(*ADMIN)),
):
    user = db.query(models.UserAccount).filter(models.UserAccount.id == user_id).first()
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id and (payload.is_active is False or (payload.role and payload.role != "system_admin")):
        raise HTTPException(400, "You cannot deactivate or demote your own account")

    changes = []
    if payload.is_active is not None and payload.is_active != user.is_active:
        user.is_active = payload.is_active
        changes.append("activated" if payload.is_active else "deactivated")
    if payload.role and payload.role != user.role.name.value:
        role = _role(db, payload.role)
        user.role_id = role.id
        db.flush()
        db.refresh(user)
        _ensure_profile(db, user, payload.role, {})
        changes.append(f"role -> {payload.role}")
    if changes:
        audit.log(db, admin.id, "user_updated", f"{user.email}: {', '.join(changes)}")
    db.commit()
    db.refresh(user)
    return _out(user)


@router.get("/audit", response_model=List[schemas.AuditLogOut])
def audit_log(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    admin: models.UserAccount = Depends(auth.require_roles(*ADMIN)),
):
    rows = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(limit).all()
    return [
        schemas.AuditLogOut(id=r.id, created_at=r.created_at, user_name=r.user.full_name if r.user else None, action=r.action, detail=r.detail)
        for r in rows
    ]
