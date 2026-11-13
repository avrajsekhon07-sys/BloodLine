import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import models, schemas, auth, audit
from ..database import get_db
from ..services import ratelimit
from ..services.donor_matching import DONATION_COOLDOWN_DAYS, days_since

router = APIRouter(prefix="/auth", tags=["auth"])

MIN_PASSWORD_LEN = 8


@router.post("/login", response_model=schemas.LoginResponse)
def login(payload: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    if ratelimit.enabled():
        wait = ratelimit.limiter.check(ip, payload.email)
        if wait:
            audit.log(db, None, "login_rate_limited", payload.email)
            db.commit()
            raise HTTPException(
                status_code=429, headers={"Retry-After": str(wait)},
                detail=f"Too many failed sign-in attempts. Try again in {max(1, round(wait / 60))} minute(s).",
            )
    user = db.query(models.UserAccount).filter(models.UserAccount.email == payload.email).first()
    if not user or not auth.verify_password(payload.password, user.hashed_password):
        ratelimit.limiter.record_failure(ip, payload.email)
        audit.log(db, user.id if user else None, "login_failed", payload.email)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        audit.log(db, user.id, "login_blocked_inactive", payload.email)
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    ratelimit.limiter.reset(ip, payload.email)
    audit.log(db, user.id, "login", payload.email)
    db.commit()
    token = auth.create_access_token({"sub": user.id})
    return schemas.LoginResponse(access_token=token, role=user.role.name.value, full_name=user.full_name)


@router.post("/register-donor", response_model=schemas.LoginResponse, status_code=201)
def register_donor(payload: schemas.RegisterDonorRequest, db: Session = Depends(get_db)):
    """Donor self-registration (FR-AUTH-4). Creates only a donor account; staff
    and admin accounts can be created by a system administrator."""
    try:
        group = models.BloodGroup(payload.blood_group)
    except ValueError:
        raise HTTPException(400, "blood_group must be one of: " + ", ".join(g.value for g in models.BloodGroup))
    if len(payload.password) < MIN_PASSWORD_LEN:
        raise HTTPException(400, f"Password must be at least {MIN_PASSWORD_LEN} characters")
    if db.query(models.UserAccount).filter(models.UserAccount.email == payload.email).first():
        raise HTTPException(400, "An account with this email already exists")
    role = db.query(models.Role).filter(models.Role.name == models.RoleName.DONOR).first()
    if role is None:
        raise HTTPException(400, "Roles are not set up — run the seed script first.")

    user = models.UserAccount(
        email=payload.email,
        hashed_password=auth.hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role_id=role.id,
    )
    db.add(user)
    db.flush()
    db.add(models.Donor(
        user_id=user.id, blood_group=group, latitude=payload.latitude, longitude=payload.longitude,
        is_available=True, notification_consent=payload.notification_consent,
    ))
    audit.log(db, user.id, "donor_registered", payload.email)
    db.commit()
    return schemas.LoginResponse(
        access_token=auth.create_access_token({"sub": user.id}), role="donor", full_name=user.full_name,
    )


@router.get("/me")
def me(user: models.UserAccount = Depends(auth.get_current_user)):
    """Who am I, and which blood bank do I work at (staff only)."""
    return {
        "full_name": user.full_name, "email": user.email, "role": user.role.name.value,
        "blood_bank_id": user.staff_profile.blood_bank_id if user.staff_profile else None,
    }


@router.get("/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    """Lists the seeded *@bloodline.demo accounts so the demo login page can offer a picker.
    Unauthenticated by design, therefore DEMO ONLY: it is switched off with BLOODLINE_DEMO_LOGIN=0
    and always off when BLOODLINE_ENV=production."""
    if os.getenv("BLOODLINE_DEMO_LOGIN", "1") != "1" or os.getenv("BLOODLINE_ENV") == "production":
        raise HTTPException(404, "Not found")
    users = db.query(models.UserAccount).filter(models.UserAccount.email.like("%@bloodline.demo")).all()
    out = []
    for u in users:
        row = {"email": u.email, "full_name": u.full_name, "role": u.role.name.value}
        d = u.donor_profile
        if d is not None:
            row.update(
                blood_group=d.blood_group.value, is_available=bool(d.is_available),
                notification_consent=bool(d.notification_consent),
                last_donation_date=d.last_donation_date.isoformat() if d.last_donation_date else None,
                cooldown_cleared=d.last_donation_date is None or days_since(d.last_donation_date) >= DONATION_COOLDOWN_DAYS,
            )
        out.append(row)
    num = lambda r: int(re.sub(r"\D", "", r["email"].split("@")[0]) or 0)
    return sorted(out, key=lambda r: (r["role"] == "donor", r["role"], num(r)))
