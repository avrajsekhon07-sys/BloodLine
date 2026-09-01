"""
Seed the local SQLite DB with demo data for the W5 walkthrough.

Run with:  python -m app.seed
"""
import datetime as dt
import random

from .database import Base, engine, SessionLocal
from . import models, auth
from .services.synthetic_data import generate_all_groups, BLOOD_GROUP_BASELINE

random.seed(42)

DEMO_PASSWORD = "bloodline123"  # same for every demo account, printed at the end


def run():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # --- Roles ---
    roles = {r.value: models.Role(name=r) for r in models.RoleName}
    db.add_all(roles.values())
    db.flush()

    # --- Blood bank ---
    bank = models.BloodBank(name="Patiala Central Blood Bank", address="Patiala, Punjab", latitude=30.34, longitude=76.38)
    db.add(bank)
    db.flush()

    # --- Demo users: manager + inventory staff + a batch of donors ---
    manager_user = models.UserAccount(
        email="manager@bloodline.demo",
        hashed_password=auth.hash_password(DEMO_PASSWORD),
        full_name="Asha Verma",
        role_id=roles["blood_bank_manager"].id,
    )
    inv_staff_user = models.UserAccount(
        email="inventory@bloodline.demo",
        hashed_password=auth.hash_password(DEMO_PASSWORD),
        full_name="Rohan Mehta",
        role_id=roles["inventory_staff"].id,
    )
    db.add_all([manager_user, inv_staff_user])
    db.flush()

    db.add(models.Staff(user_id=inv_staff_user.id, blood_bank_id=bank.id, designation="inventory_staff"))
    db.add(models.Staff(user_id=manager_user.id, blood_bank_id=bank.id, designation="blood_bank_manager"))

    # --- Admin + medical (screening) staff ---
    admin_user = models.UserAccount(
        email="admin@bloodline.demo",
        hashed_password=auth.hash_password(DEMO_PASSWORD),
        full_name="Ritu Kohli",
        role_id=roles["system_admin"].id,
    )
    medical_user = models.UserAccount(
        email="screening@bloodline.demo",
        hashed_password=auth.hash_password(DEMO_PASSWORD),
        full_name="Dr. Naveen Oberoi",
        role_id=roles["medical_staff"].id,
    )
    db.add_all([admin_user, medical_user])
    db.flush()
    db.add(models.Staff(user_id=medical_user.id, blood_bank_id=bank.id, designation="medical_staff"))

    # --- Hospital + hospital coordinator ---
    hospital = models.Hospital(name="Rajindra Government Hospital", address="Patiala, Punjab")
    db.add(hospital)
    db.flush()

    hospital_user = models.UserAccount(
        email="hospital@bloodline.demo",
        hashed_password=auth.hash_password(DEMO_PASSWORD),
        full_name="Dr. Simran Bedi",
        role_id=roles["hospital_coordinator"].id,
    )
    db.add(hospital_user)
    db.flush()
    db.add(models.HospitalUser(user_id=hospital_user.id, hospital_id=hospital.id))
    db.flush()

    # --- Donors (mix of blood groups, availability, consent, cooldown status) ---
    donor_names = [
        "Priya Sharma", "Arjun Singh", "Simran Kaur", "Vikram Rao", "Neha Gupta",
        "Karan Malhotra", "Isha Kapoor", "Aditya Joshi", "Meera Nair", "Rahul Bansal",
        "Anjali Chopra", "Sanjay Dutta", "Tanvi Bhatia", "Yash Sethi", "Divya Menon",
    ]
    blood_groups = list(BLOOD_GROUP_BASELINE.keys())
    today = dt.date.today()

    for i, name in enumerate(donor_names):
        u = models.UserAccount(
            email=f"donor{i+1}@bloodline.demo",
            hashed_password=auth.hash_password(DEMO_PASSWORD),
            full_name=name,
            role_id=roles["donor"].id,
        )
        db.add(u)
        db.flush()

        # vary donation recency: some eligible (>90d), some in cooldown, some never donated
        last_donation = None
        r = random.random()
        if r < 0.5:
            last_donation = today - dt.timedelta(days=random.randint(91, 400))
        elif r < 0.75:
            last_donation = today - dt.timedelta(days=random.randint(1, 89))
        # else: None (never donated)

        donor = models.Donor(
            user_id=u.id,
            blood_group=random.choice(blood_groups),
            last_donation_date=last_donation,
            is_available=random.random() < 0.8,
            notification_consent=random.random() < 0.85,
            latitude=30.34 + random.uniform(-0.05, 0.05),
            longitude=76.38 + random.uniform(-0.05, 0.05),
        )
        db.add(donor)

    db.flush()

    # --- Inventory: seed with intentionally mixed stock levels (some tight, some healthy) ---
    stock_overrides = {"B+": 20, "O-": 4, "AB-": 2}  # deliberately tight to demonstrate HIGH risk
    for bg in blood_groups:
        qty = stock_overrides.get(bg, random.randint(25, 60))
        db.add(models.Inventory(blood_bank_id=bank.id, blood_group=bg, component="whole_blood", quantity_units=qty))

    db.flush()

    # --- Sample blood requests (mixed statuses so the manager queue isn't empty) ---
    db.add(models.BloodRequest(
        hospital_id=hospital.id, blood_group="B+", quantity_units=10,
        urgency="emergency", status="pending", notes="Trauma ward — multiple casualties expected.",
    ))
    db.add(models.BloodRequest(
        hospital_id=hospital.id, blood_group="O-", quantity_units=4,
        urgency="urgent", status="pending", notes="Scheduled surgery tomorrow.",
    ))
    db.add(models.BloodRequest(
        hospital_id=hospital.id, blood_group="A+", quantity_units=6,
        urgency="routine", status="fulfilled", notes=None,
    ))

    # --- Sample screening record so the screening history page isn't empty ---
    medical_staff = db.query(models.Staff).filter(models.Staff.user_id == medical_user.id).first()
    first_donor = db.query(models.Donor).first()
    if medical_staff and first_donor:
        db.add(models.ScreeningRecord(
            donor_id=first_donor.id,
            performed_by_id=medical_staff.id,
            outcome="eligible",
            notes="Routine pre-donation screening — no deferral criteria met.",
        ))

    # --- Synthetic demand history: 180 days per blood group, clearly labelled ---
    start = today - dt.timedelta(days=180)
    all_series = generate_all_groups(str(start), days=180)
    for bg, df in all_series.items():
        for _, row in df.iterrows():
            db.add(models.DemandHistory(
                blood_bank_id=bank.id,
                blood_group=bg,
                date=row["date"],
                units_demanded=float(row["units_demanded"]),
                is_synthetic=True,
            ))

    bank_id = bank.id
    db.commit()
    db.close()

    print("Seed complete.")
    print(f"Blood bank id: {bank_id}")
    print("Demo accounts (all use password:", DEMO_PASSWORD, "):")
    print("  Manager:              manager@bloodline.demo")
    print("  Inventory staff:      inventory@bloodline.demo")
    print("  Medical/screening:    screening@bloodline.demo")
    print("  Hospital coordinator: hospital@bloodline.demo")
    print("  System admin:         admin@bloodline.demo")
    print("  Donors:                donor1@bloodline.demo ... donor15@bloodline.demo")


if __name__ == "__main__":
    run()
