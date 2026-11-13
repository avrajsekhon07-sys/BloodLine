from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


# ---- Auth ----

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str


# ---- Inventory ----

class InventoryOut(BaseModel):
    id: str
    blood_bank_id: str
    blood_group: str
    component: str
    quantity_units: int
    last_updated: datetime

    class Config:
        from_attributes = True


class InventoryTransactionIn(BaseModel):
    blood_bank_id: str
    blood_group: str
    component: str = "whole_blood"
    txn_type: str  # receipt | issue | expiry | discard
    quantity_units: int
    note: Optional[str] = None


class InventoryTransactionOut(BaseModel):
    id: str
    blood_group: str
    component: str
    txn_type: str
    quantity_units: int
    note: Optional[str]
    created_at: datetime


# ---- Demand / forecast / risk ----

class DemandPoint(BaseModel):
    date: date
    units_demanded: float

    class Config:
        from_attributes = True


class ForecastOut(BaseModel):
    blood_group: str
    model_name: str
    horizon_days: int
    predicted_units: float
    baseline_units: float
    baseline_model_name: str
    improvement_over_baseline_pct: Optional[float]
    mae_baseline: Optional[float] = None
    mae_candidate: Optional[float] = None
    rmse_baseline: Optional[float] = None
    rmse_candidate: Optional[float] = None
    backtest_days: Optional[int] = None
    candidates: Optional[List[dict]] = None  # every model compared: name, mae, rmse, predicted_units, selected


class RiskOut(BaseModel):
    blood_bank_id: str
    blood_group: str
    current_stock: int
    predicted_demand: float
    shortfall: float
    risk_level: str
    explanation: str


# ---- Donor matching ----

class DonorMatchOut(BaseModel):
    donor_id: str
    full_name: str
    blood_group: str
    days_since_last_donation: Optional[int]
    is_available: bool
    notification_consent: bool
    match_score: float
    reasons: List[str]
    distance_km: Optional[float] = None


# ---- Blood requests (hospital <-> manager) ----

class BloodRequestCreate(BaseModel):
    blood_group: str
    component: str = "whole_blood"
    quantity_units: int
    urgency: str = "routine"  # routine | urgent | emergency
    notes: Optional[str] = None


class BloodRequestOut(BaseModel):
    id: str
    hospital_id: str
    hospital_name: str
    blood_group: str
    component: str
    quantity_units: int
    urgency: str
    status: str
    notes: Optional[str]
    created_at: datetime


# ---- Screening ----

class ScreeningRecordCreate(BaseModel):
    donor_id: str
    outcome: str  # eligible | deferred | rejected
    notes: Optional[str] = None


class ScreeningRecordOut(BaseModel):
    id: str
    donor_id: str
    donor_name: str
    donor_blood_group: str
    performed_by_name: str
    outcome: str
    notes: Optional[str]
    recorded_at: datetime


class ScreeningCandidateOut(BaseModel):
    donor_id: str
    full_name: str
    blood_group: str
    days_since_last_donation: Optional[int]
    cooldown_cleared: bool
    is_available: bool
    notification_consent: bool
    last_screening_outcome: Optional[str]
    last_screened_at: Optional[datetime]


# ---- Donor self-service ----

class DonationOut(BaseModel):
    id: str
    donation_date: date
    units_collected: int


class DonorProfileOut(BaseModel):
    donor_id: str
    full_name: str
    email: str
    blood_group: str
    is_available: bool
    notification_consent: bool
    last_donation_date: Optional[date]
    days_since_last_donation: Optional[int]
    cooldown_cleared: bool
    donations: List[DonationOut]


class DonorAvailabilityUpdate(BaseModel):
    is_available: bool
    notification_consent: bool


# ---- Admin ----

class AdminUserOut(BaseModel):
    id: str
    full_name: str
    email: str
    role: str
    is_active: bool


class AdminSummaryOut(BaseModel):
    total_users: int
    total_donors: int
    total_hospitals: int
    total_blood_banks: int
    users_by_role: dict


# ---- Reports / analytics ----

class ReportsSummaryOut(BaseModel):
    blood_bank_id: str
    total_inventory_units: int
    units_received: int
    units_issued: int
    units_expired_discarded: int
    high_risk_groups: List[str]
    moderate_risk_groups: List[str]
    demand_summary: dict  # blood_group -> avg daily demand
    forecast_summary: dict  # blood_group -> 7-day predicted units
    inventory_by_group: dict  # blood_group -> current stock
    requests_summary: dict  # status -> count


# ---------------------------------------------------------------------------
# Added after W6: registration, admin, donations, notifications, risk history
# ---------------------------------------------------------------------------
class RegisterDonorRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    blood_group: str
    notification_consent: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class AdminUserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str
    blood_bank_id: Optional[str] = None  # staff roles (default: first bank)
    hospital_id: Optional[str] = None    # hospital_coordinator (default: first hospital)
    blood_group: Optional[str] = None    # donor


class AdminUserUpdate(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None


class AuditLogOut(BaseModel):
    id: str
    created_at: datetime
    user_name: Optional[str]
    action: str
    detail: Optional[str]


class DonationCreate(BaseModel):
    donor_id: str
    units_collected: int = 1
    blood_bank_id: Optional[str] = None
    donation_date: Optional[date] = None


class DonationRecordedOut(BaseModel):
    id: str
    donor_id: str
    donor_name: str
    blood_group: str
    units_collected: int
    donation_date: date
    new_stock: Optional[int] = None


class ReadyDonorOut(BaseModel):
    donor_id: str
    full_name: str
    blood_group: str
    screened_at: datetime


class OutreachRequest(BaseModel):
    blood_group: str
    message: Optional[str] = None
    radius_km: Optional[float] = None


class OutreachOut(BaseModel):
    matched: int
    notified: int
    skipped_recently_notified: int
    pushed: int = 0  # browser push messages delivered (0 when push isn't configured)
    push_failed: int = 0
    push_no_subscription: int = 0


class NotificationOut(BaseModel):
    id: str
    message: str
    sent_at: datetime
    was_read: bool


class AlertHistoryOut(BaseModel):
    created_at: datetime
    blood_group: str
    risk_level: str
    current_stock: int
    predicted_demand: float
    shortfall: float
