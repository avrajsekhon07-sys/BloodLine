"""Add the original synthetic demo fixture without touching existing records.

Run once after Alembic migrations with BLOODLINE_FACULTY_DEMO=1:
    python -m app.bootstrap_demo

This is intentionally separate from ``app.seed`` (which drops tables and is
restricted to disposable local SQLite databases). Demo accounts receive
unusable random password hashes; the public picker uses the restricted demo
login endpoint instead of a shared password.
"""
import datetime as dt
import os
import random
import secrets

from sqlalchemy.exc import IntegrityError

from . import auth, models
from .database import SessionLocal
from .services import units as units_svc
from .services.synthetic_data import BLOOD_GROUP_BASELINE, generate_all_groups

DONOR_NAMES = (
    "Priya Sharma", "Arjun Singh", "Simran Kaur", "Vikram Rao", "Neha Gupta",
    "Karan Malhotra", "Isha Kapoor", "Aditya Joshi", "Meera Nair", "Rahul Bansal",
    "Anjali Chopra", "Sanjay Dutta", "Tanvi Bhatia", "Yash Sethi", "Divya Menon",
)
STAFF = (
    ("manager@bloodline.demo", "Asha Verma", models.RoleName.BLOOD_BANK_MANAGER, "blood_bank_manager"),
    ("inventory@bloodline.demo", "Rohan Mehta", models.RoleName.INVENTORY_STAFF, "inventory_staff"),
    ("screening@bloodline.demo", "Dr. Naveen Oberoi", models.RoleName.MEDICAL_STAFF, "medical_staff"),
    ("hospital@bloodline.demo", "Dr. Simran Bedi", models.RoleName.HOSPITAL_COORDINATOR, "hospital_coordinator"),
    ("admin@bloodline.demo", "Ritu Kohli", models.RoleName.SYSTEM_ADMIN, "system_admin"),
)
BANKS = (
    ("Patiala Central Blood Bank", "Patiala, Punjab", 30.34, 76.38, 1.0, {"B+": 20, "O-": 4, "AB-": 2}),
    ("Demo Blood Bank - Ludhiana (synthetic)", "Synthetic demo location", 30.90, 75.85, 0.7, {"O-": 40, "AB-": 18, "B+": 55}),
    ("Demo Blood Bank - Chandigarh (synthetic)", "Synthetic demo location", 30.73, 76.78, 0.9, {"O-": 22, "AB-": 3}),
)
HOSPITAL_NAME = "Rajindra Government Hospital"


def _role(db, role_name):
    role = db.query(models.Role).filter(models.Role.name == role_name).first()
    if role is None:
        raise RuntimeError("Roles are missing; run `alembic upgrade head` and `python -m app.bootstrap` first.")
    return role


def _demo_user(db, email, full_name, role_name, counts):
    user = db.query(models.UserAccount).filter(models.UserAccount.email == email).first()
    if user is not None:
        if not user.is_demo or user.role.name != role_name:
            raise RuntimeError(f"Refusing to claim or alter existing non-demo account {email}.")
        return user
    user = models.UserAccount(
        email=email,
        hashed_password=auth.hash_password(secrets.token_urlsafe(32)),
        full_name=full_name,
        role_id=_role(db, role_name).id,
        is_active=True,
        is_demo=True,
    )
    db.add(user)
    db.flush()
    counts["users"] += 1
    return user


def _demo_bank(db, spec, counts):
    name, address, lat, lon, scale, overrides = spec
    bank = db.query(models.BloodBank).filter_by(name=name, is_demo=True).first()
    if bank is None:
        bank = models.BloodBank(name=name, address=address, latitude=lat, longitude=lon, is_demo=True)
        db.add(bank)
        db.flush()
        counts["banks"] += 1
    return bank, scale, overrides


def _seed_units(db, inventory, today, rng):
    qty = inventory.quantity_units
    a, b = int(qty * 0.6), int(qty * 0.3)
    for n, age in ((a, rng.randint(1, 14)), (b, rng.randint(15, 27)), (qty - a - b, rng.randint(28, 33))):
        if n > 0:
            units_svc.add_units(db, inventory, n, today - dt.timedelta(days=age))


def bootstrap_demo_database(today=None):
    """Create exactly five role accounts, fifteen donors, and synthetic workflows.

    Existing matching demo rows are left as-is. If a reserved demo email is
    already owned by a non-demo account, the whole operation aborts safely.
    """
    if os.getenv("BLOODLINE_FACULTY_DEMO") != "1":
        raise RuntimeError("Set BLOODLINE_FACULTY_DEMO=1 before provisioning the synthetic demo accounts.")
    today = today or dt.date.today()
    db = SessionLocal()
    counts = {"users": 0, "donors": 0, "banks": 0, "inventory": 0, "demand": 0, "requests": 0}
    try:
        for role in models.RoleName:
            _role(db, role)
        bank_rows = [_demo_bank(db, spec, counts) for spec in BANKS]
        main_bank = bank_rows[0][0]

        users = {}
        for email, name, role_name, designation in STAFF:
            user = _demo_user(db, email, name, role_name, counts)
            users[email] = user
            if designation in ("blood_bank_manager", "inventory_staff", "medical_staff"):
                profile = db.query(models.Staff).filter_by(user_id=user.id).first()
                if profile is None:
                    db.add(models.Staff(user_id=user.id, blood_bank_id=main_bank.id, designation=designation))
            elif designation == "hospital_coordinator":
                pass

        hospital = db.query(models.Hospital).filter_by(name=HOSPITAL_NAME, is_demo=True).first()
        if hospital is None:
            hospital = models.Hospital(name=HOSPITAL_NAME, address="Synthetic demo location", is_demo=True)
            db.add(hospital)
            db.flush()
        hospital_user = users["hospital@bloodline.demo"]
        if db.query(models.HospitalUser).filter_by(user_id=hospital_user.id).first() is None:
            db.add(models.HospitalUser(user_id=hospital_user.id, hospital_id=hospital.id))

        rng = random.Random(42)
        blood_groups = list(BLOOD_GROUP_BASELINE)
        for i, name in enumerate(DONOR_NAMES, start=1):
            email = f"donor{i}@bloodline.demo"
            user = _demo_user(db, email, name, models.RoleName.DONOR, counts)
            if db.query(models.Donor).filter_by(user_id=user.id).first() is None:
                last_donation = None
                r = rng.random()
                if r < 0.5:
                    last_donation = today - dt.timedelta(days=rng.randint(91, 400))
                elif r < 0.75:
                    last_donation = today - dt.timedelta(days=rng.randint(1, 89))
                db.add(models.Donor(
                    user_id=user.id, blood_group=rng.choice(blood_groups), last_donation_date=last_donation,
                    is_available=rng.random() < 0.8, notification_consent=rng.random() < 0.85,
                    latitude=30.34 + rng.uniform(-0.05, 0.05), longitude=76.38 + rng.uniform(-0.05, 0.05),
                ))
                counts["donors"] += 1
        db.flush()

        start = today - dt.timedelta(days=179)
        all_series = generate_all_groups(str(start), days=180)
        for bank, scale, overrides in bank_rows:
            for bg in blood_groups:
                slot = db.query(models.Inventory).filter_by(
                    blood_bank_id=bank.id, blood_group=bg, component="whole_blood"
                ).first()
                if slot is None:
                    qty = overrides.get(bg, rng.randint(25, 60))
                    slot = models.Inventory(
                        blood_bank_id=bank.id, blood_group=bg, component="whole_blood", quantity_units=qty,
                    )
                    db.add(slot)
                    db.flush()
                    _seed_units(db, slot, today, rng)
                    counts["inventory"] += 1
                for row in all_series[bg].itertuples(index=False):
                    exists = db.query(models.DemandHistory.id).filter_by(
                        blood_bank_id=bank.id, blood_group=bg, date=row.date,
                    ).first()
                    if exists is None:
                        db.add(models.DemandHistory(
                            blood_bank_id=bank.id, blood_group=bg, date=row.date,
                            units_demanded=round(float(row.units_demanded) * scale, 1), is_synthetic=True,
                        ))
                        counts["demand"] += 1

        request_specs = (
            ("B+", 10, "emergency", "pending", "Synthetic trauma scenario."),
            ("O-", 4, "urgent", "pending", "Synthetic urgent scenario."),
            ("A+", 6, "routine", "fulfilled", None),
        )
        existing_requests = db.query(models.BloodRequest).filter_by(hospital_id=hospital.id).all()
        existing_request_keys = {
            (r.blood_group.value if hasattr(r.blood_group, "value") else r.blood_group,
             r.quantity_units, r.urgency, r.status)
            for r in existing_requests
        }
        for bg, quantity, urgency, status, notes in request_specs:
            if (bg, quantity, urgency, status) not in existing_request_keys:
                db.add(models.BloodRequest(
                    hospital_id=hospital.id, blood_group=bg, quantity_units=quantity,
                    urgency=urgency, status=status, notes=notes,
                ))
                counts["requests"] += 1

        medical = users["screening@bloodline.demo"]
        medical_staff = db.query(models.Staff).filter_by(user_id=medical.id).first()
        first_donor = db.query(models.Donor).join(models.UserAccount).filter(
            models.UserAccount.is_demo.is_(True)
        ).order_by(models.UserAccount.email).first()
        if medical_staff and first_donor and db.query(models.ScreeningRecord).filter_by(donor_id=first_donor.id).first() is None:
            db.add(models.ScreeningRecord(
                donor_id=first_donor.id, performed_by_id=medical_staff.id, outcome="eligible",
                notes="Synthetic demonstration screening record.",
            ))

        db.commit()
        return counts
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    try:
        counts = bootstrap_demo_database()
    except IntegrityError as exc:
        raise RuntimeError("Demo provisioning hit a uniqueness conflict; its transaction was rolled back.") from exc
    print("Synthetic demo provisioning complete. Added counts:", counts)
    print("Exactly five non-donor accounts and fifteen donor accounts are supported; no real data was used.")


if __name__ == "__main__":
    main()
