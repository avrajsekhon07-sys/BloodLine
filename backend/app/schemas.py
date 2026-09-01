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
