"""
ORM models for BloodLine.

Scope note: every entity from the project proposal is modelled here so the
schema doesn't need to change shape when later-phase features (hospital
requests, screening workflow, notifications, reports) are built. Only the
tables needed for the W5/MST vertical slice (UserAccount, Role, Donor,
BloodBank, Inventory, InventoryTransaction, DemandHistory, Prediction,
Alert, Donation) are actually read/written by the W5 API routes.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Date, ForeignKey,
    Enum, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship

from .database import Base


def gen_id():
    return str(uuid.uuid4())


class BloodGroup(str, enum.Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


class RoleName(str, enum.Enum):
    DONOR = "donor"
    BLOOD_BANK_MANAGER = "blood_bank_manager"
    INVENTORY_STAFF = "inventory_staff"
    MEDICAL_STAFF = "medical_staff"
    HOSPITAL_COORDINATOR = "hospital_coordinator"
    SYSTEM_ADMIN = "system_admin"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


# ---------------------------------------------------------------------------
# Identity / roles
# ---------------------------------------------------------------------------

class Role(Base):
    __tablename__ = "roles"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(Enum(RoleName), unique=True, nullable=False)

    users = relationship("UserAccount", back_populates="role")


class UserAccount(Base):
    __tablename__ = "user_accounts"
    id = Column(String, primary_key=True, default=gen_id)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role_id = Column(String, ForeignKey("roles.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    role = relationship("Role", back_populates="users")
    donor_profile = relationship("Donor", back_populates="user", uselist=False)
    staff_profile = relationship("Staff", back_populates="user", uselist=False)
    hospital_user_profile = relationship("HospitalUser", back_populates="user", uselist=False)


# ---------------------------------------------------------------------------
# Donor
# ---------------------------------------------------------------------------

class Donor(Base):
    __tablename__ = "donors"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("user_accounts.id"), unique=True, nullable=False)
    blood_group = Column(Enum(BloodGroup), nullable=False)
    last_donation_date = Column(Date, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_available = Column(Boolean, default=True)
    notification_consent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserAccount", back_populates="donor_profile")
    donations = relationship("Donation", back_populates="donor")
    availability_log = relationship("DonorAvailability", back_populates="donor")
    notifications = relationship("DonorNotification", back_populates="donor")


class DonorAvailability(Base):
    """Later-phase: fine-grained availability windows. Present now for schema stability."""
    __tablename__ = "donor_availability"
    id = Column(String, primary_key=True, default=gen_id)
    donor_id = Column(String, ForeignKey("donors.id"), nullable=False)
    available_from = Column(DateTime, nullable=False)
    available_to = Column(DateTime, nullable=True)

    donor = relationship("Donor", back_populates="availability_log")


class DonorNotification(Base):
    """Later-phase: outbound alerts to donors."""
    __tablename__ = "donor_notifications"
    id = Column(String, primary_key=True, default=gen_id)
    donor_id = Column(String, ForeignKey("donors.id"), nullable=False)
    alert_id = Column(String, ForeignKey("alerts.id"), nullable=True)
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    was_read = Column(Boolean, default=False)

    donor = relationship("Donor", back_populates="notifications")


# ---------------------------------------------------------------------------
# Blood bank / staff
# ---------------------------------------------------------------------------

class BloodBank(Base):
    __tablename__ = "blood_banks"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String, nullable=True)

    inventory_items = relationship("Inventory", back_populates="blood_bank")
    demand_history = relationship("DemandHistory", back_populates="blood_bank")
    predictions = relationship("Prediction", back_populates="blood_bank")
    alerts = relationship("Alert", back_populates="blood_bank")
    staff = relationship("Staff", back_populates="blood_bank")


class Staff(Base):
    __tablename__ = "staff"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("user_accounts.id"), unique=True, nullable=False)
    blood_bank_id = Column(String, ForeignKey("blood_banks.id"), nullable=False)
    designation = Column(String, nullable=False)  # e.g. "inventory_staff", "medical_staff"

    user = relationship("UserAccount", back_populates="staff_profile")
    blood_bank = relationship("BloodBank", back_populates="staff")
    screening_records = relationship("ScreeningRecord", back_populates="performed_by")


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

class Inventory(Base):
    """Current stock snapshot per (blood_bank, blood_group, component)."""
    __tablename__ = "inventory"
    id = Column(String, primary_key=True, default=gen_id)
    blood_bank_id = Column(String, ForeignKey("blood_banks.id"), nullable=False)
    blood_group = Column(Enum(BloodGroup), nullable=False)
    component = Column(String, default="whole_blood")
    quantity_units = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("blood_bank_id", "blood_group", "component", name="uq_inventory_slot"),
    )

    blood_bank = relationship("BloodBank", back_populates="inventory_items")
    transactions = relationship("InventoryTransaction", back_populates="inventory")
    blood_units = relationship("BloodUnit", back_populates="inventory")


class BloodUnit(Base):
    """Individual traceable unit (collection/expiry tracking)."""
    __tablename__ = "blood_units"
    id = Column(String, primary_key=True, default=gen_id)
    inventory_id = Column(String, ForeignKey("inventory.id"), nullable=False)
    collected_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False)
    status = Column(String, default="available")  # available | issued | expired | discarded

    inventory = relationship("Inventory", back_populates="blood_units")


class InventoryTransaction(Base):
    """Every stock movement — receipt, issue, expiry/discard."""
    __tablename__ = "inventory_transactions"
    id = Column(String, primary_key=True, default=gen_id)
    inventory_id = Column(String, ForeignKey("inventory.id"), nullable=False)
    txn_type = Column(String, nullable=False)  # receipt | issue | expiry | discard
    quantity_units = Column(Integer, nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    inventory = relationship("Inventory", back_populates="transactions")


class Donation(Base):
    __tablename__ = "donations"
    id = Column(String, primary_key=True, default=gen_id)
    donor_id = Column(String, ForeignKey("donors.id"), nullable=False)
    blood_bank_id = Column(String, ForeignKey("blood_banks.id"), nullable=False)
    donation_date = Column(Date, default=datetime.utcnow)
    units_collected = Column(Integer, default=1)

    donor = relationship("Donor", back_populates="donations")


class ScreeningRecord(Base):
    """Later-phase medical screening workflow. Never auto-decides eligibility."""
    __tablename__ = "screening_records"
    id = Column(String, primary_key=True, default=gen_id)
    donor_id = Column(String, ForeignKey("donors.id"), nullable=False)
    performed_by_id = Column(String, ForeignKey("staff.id"), nullable=False)
    outcome = Column(String, nullable=False)  # eligible | deferred | rejected
    notes = Column(Text, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    performed_by = relationship("Staff", back_populates="screening_records")


# ---------------------------------------------------------------------------
# Demand / forecasting / risk
# ---------------------------------------------------------------------------

class DemandHistory(Base):
    """Synthetic/simulated daily demand — clearly labelled, never presented as real."""
    __tablename__ = "demand_history"
    id = Column(String, primary_key=True, default=gen_id)
    blood_bank_id = Column(String, ForeignKey("blood_banks.id"), nullable=False)
    blood_group = Column(Enum(BloodGroup), nullable=False)
    date = Column(Date, nullable=False)
    units_demanded = Column(Float, nullable=False)
    is_synthetic = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("blood_bank_id", "blood_group", "date", name="uq_demand_day"),
    )

    blood_bank = relationship("BloodBank", back_populates="demand_history")


class Prediction(Base):
    """A forecasting run's output for one blood group, with the baseline it beat (or didn't)."""
    __tablename__ = "predictions"
    id = Column(String, primary_key=True, default=gen_id)
    blood_bank_id = Column(String, ForeignKey("blood_banks.id"), nullable=False)
    blood_group = Column(Enum(BloodGroup), nullable=False)
    model_name = Column(String, nullable=False)  # e.g. "exp_smoothing" | "naive_baseline"
    horizon_days = Column(Integer, default=7)
    predicted_units = Column(Float, nullable=False)
    baseline_units = Column(Float, nullable=True)
    mae_vs_baseline = Column(Float, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)

    blood_bank = relationship("BloodBank", back_populates="predictions")


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True, default=gen_id)
    blood_bank_id = Column(String, ForeignKey("blood_banks.id"), nullable=False)
    blood_group = Column(Enum(BloodGroup), nullable=False)
    risk_level = Column(Enum(RiskLevel), nullable=False)
    current_stock = Column(Integer, nullable=False)
    predicted_demand = Column(Float, nullable=False)
    shortfall = Column(Float, nullable=False)
    explanation = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    blood_bank = relationship("BloodBank", back_populates="alerts")


# ---------------------------------------------------------------------------
# Hospitals (later-phase, schema present now)
# ---------------------------------------------------------------------------

class Hospital(Base):
    __tablename__ = "hospitals"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)

    hospital_users = relationship("HospitalUser", back_populates="hospital")
    requests = relationship("BloodRequest", back_populates="hospital")


class HospitalUser(Base):
    __tablename__ = "hospital_users"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("user_accounts.id"), unique=True, nullable=False)
    hospital_id = Column(String, ForeignKey("hospitals.id"), nullable=False)

    user = relationship("UserAccount", back_populates="hospital_user_profile")
    hospital = relationship("Hospital", back_populates="hospital_users")


class BloodRequest(Base):
    __tablename__ = "blood_requests"
    id = Column(String, primary_key=True, default=gen_id)
    hospital_id = Column(String, ForeignKey("hospitals.id"), nullable=False)
    blood_group = Column(Enum(BloodGroup), nullable=False)
    component = Column(String, default="whole_blood")
    quantity_units = Column(Integer, nullable=False)
    urgency = Column(String, default="routine")  # routine | urgent | emergency
    status = Column(String, default="pending")  # pending | fulfilled | rejected | cancelled
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    hospital = relationship("Hospital", back_populates="requests")


class Report(Base):
    """Later-phase: saved/exported manager reports."""
    __tablename__ = "reports"
    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String, nullable=False)
    generated_by_id = Column(String, ForeignKey("user_accounts.id"), nullable=False)
    content_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
