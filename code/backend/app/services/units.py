"""Single-unit tracking with collection and expiry dates (FR-INV-6).

Shelf lives below are common defaults for planning only. They are NOT medical
guidance: each blood centre must set its own via BLOODLINE_SHELF_<COMPONENT>
environment variables (days), e.g. BLOODLINE_SHELF_PLATELETS=5.
Issues, expiries and discards consume the unit that expires first (FEFO).
"""
import os
from datetime import date, timedelta


DEFAULT_SHELF_LIFE_DAYS = {"whole_blood": 35, "red_cells": 42, "platelets": 5, "plasma": 365}


def shelf_life_days(component: str) -> int:
    env = os.getenv(f"BLOODLINE_SHELF_{str(component).upper()}")
    if env and env.isdigit():
        return int(env)
    return DEFAULT_SHELF_LIFE_DAYS.get(component, 35)


def add_units(db, inv, qty: int, collected: date = None):
    from .. import models  # imported lazily so the pure helpers above work without a database stack
    collected = collected or date.today()
    expiry = collected + timedelta(days=shelf_life_days(inv.component))
    for _ in range(int(qty)):
        db.add(models.BloodUnit(inventory_id=inv.id, collected_date=collected, expiry_date=expiry, status="available"))


def consume_units(db, inv, qty: int, new_status: str) -> int:
    """Mark up to `qty` available units (earliest expiry first). Returns how many were tracked;
    stock that pre-dates unit tracking has no unit rows and is simply not counted here."""
    from .. import models

    units = (
        db.query(models.BloodUnit)
        .filter(models.BloodUnit.inventory_id == inv.id, models.BloodUnit.status == "available")
        .order_by(models.BloodUnit.expiry_date.asc())
        .limit(int(qty))
        .all()
    )
    for u in units:
        u.status = new_status
    return len(units)
