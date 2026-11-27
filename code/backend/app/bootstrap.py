"""Safely add the initial production account and synthetic planning data.

For production, run after Alembic migrations with BLOODLINE_BOOTSTRAP_ADMIN_EMAIL and
BLOODLINE_BOOTSTRAP_ADMIN_PASSWORD set. For an empty local database, the CLI prompts for them. This command is additive and
idempotent; it never drops tables or modifies existing accounts, stock, or
demand rows. It creates no donor or patient records.
"""
import datetime as dt
import getpass
import os
import zlib

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.exc import IntegrityError

from . import auth, models
from .database import Base, SessionLocal, engine
from .services.synthetic_data import BLOOD_GROUP_BASELINE, generate_demand_series

SYNTHETIC_BANKS = (
    ("BloodLine Synthetic Region North", 31.0, 76.0, 1.0),
    ("BloodLine Synthetic Region Central", 30.5, 76.5, 0.8),
    ("BloodLine Synthetic Region South", 30.0, 77.0, 0.9),
)
INVENTORY_QUANTITIES = {"A+": 42, "A-": 18, "B+": 35, "B-": 16, "AB+": 14, "AB-": 8, "O+": 48, "O-": 12}
HISTORY_DAYS = 180


def _admin_credentials():
    email = os.getenv("BLOODLINE_BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("BLOODLINE_BOOTSTRAP_ADMIN_PASSWORD", "")
    if not email:
        email = input("Initial administrator email: ").strip().lower()
    if not password:
        password = getpass.getpass("Initial administrator password (16-72 UTF-8 bytes): ")
    try:
        email = validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise ValueError("BLOODLINE_BOOTSTRAP_ADMIN_EMAIL must be a valid email address.") from exc
    if len(password) < 16 or len(password.encode("utf-8")) > 72:
        raise ValueError("Initial administrator password must contain 16-72 UTF-8 bytes.")
    return email, password


def bootstrap_database(email: str, password: str, today: dt.date | None = None) -> dict:
    """Ensure roles, a first admin, and synthetic inventory/history exist."""
    if len(password) < 16 or len(password.encode("utf-8")) > 72:
        raise ValueError("Initial administrator password must contain 16-72 UTF-8 bytes.")
    today = today or dt.date.today()
    # The normal deployment path has already applied Alembic. create_all with
    # checkfirst is also safe for empty local SQLite databases.
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = SessionLocal()
    created = {"roles": 0, "admin": False, "banks": 0, "inventory": 0, "demand": 0}
    try:
        roles = {}
        for role_name in models.RoleName:
            role = db.query(models.Role).filter(models.Role.name == role_name).first()
            if role is None:
                role = models.Role(name=role_name)
                db.add(role)
                db.flush()
                created["roles"] += 1
            roles[role_name.value] = role

        existing = db.query(models.UserAccount).filter(models.UserAccount.email == email).first()
        if existing is None:
            db.add(models.UserAccount(
                email=email, hashed_password=auth.hash_password(password),
                full_name=os.getenv("BLOODLINE_BOOTSTRAP_ADMIN_NAME", "BloodLine Administrator").strip() or "BloodLine Administrator",
                role_id=roles[models.RoleName.SYSTEM_ADMIN.value].id, is_active=True,
            ))
            created["admin"] = True
        elif existing.role.name != models.RoleName.SYSTEM_ADMIN:
            raise ValueError("That email belongs to an existing non-administrator account; no account was changed.")

        start = today - dt.timedelta(days=HISTORY_DAYS - 1)
        for bank_name, latitude, longitude, scale in SYNTHETIC_BANKS:
            bank = db.query(models.BloodBank).filter(models.BloodBank.name == bank_name).first()
            if bank is None:
                bank = models.BloodBank(name=bank_name, address="Synthetic planning location", latitude=latitude, longitude=longitude)
                db.add(bank)
                db.flush()
                created["banks"] += 1
            for blood_group in BLOOD_GROUP_BASELINE:
                group = models.BloodGroup(blood_group)
                inventory = db.query(models.Inventory).filter_by(
                    blood_bank_id=bank.id, blood_group=group, component="whole_blood"
                ).first()
                if inventory is None:
                    db.add(models.Inventory(
                        blood_bank_id=bank.id, blood_group=group, component="whole_blood",
                        quantity_units=INVENTORY_QUANTITIES[blood_group],
                    ))
                    created["inventory"] += 1
                group_id = f"{bank_name}:{blood_group}".encode()
                series = generate_demand_series(
                    blood_group, start.isoformat(), days=HISTORY_DAYS, seed=zlib.crc32(group_id)
                )
                existing_dates = {row[0] for row in db.query(models.DemandHistory.date).filter_by(
                    blood_bank_id=bank.id, blood_group=group
                ).all()}
                for row in series.itertuples(index=False):
                    if row.date in existing_dates:
                        continue
                    db.add(models.DemandHistory(
                        blood_bank_id=bank.id, blood_group=group, date=row.date,
                        units_demanded=round(float(row.units_demanded) * scale, 1), is_synthetic=True,
                    ))
                    created["demand"] += 1
        db.commit()
        return created
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    email, password = _admin_credentials()
    try:
        result = bootstrap_database(email, password)
    except IntegrityError as exc:
        raise RuntimeError("Bootstrap encountered a database uniqueness conflict; no partial transaction was committed.") from exc
    print("Bootstrap complete. Added counts:", result)
    print("Demand and inventory are synthetic. No donor or patient records were created.")
    print("Unset BLOODLINE_BOOTSTRAP_ADMIN_PASSWORD from the service environment after this one-time operation.")


if __name__ == "__main__":
    main()
