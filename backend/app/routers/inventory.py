from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/inventory", tags=["inventory"])

STAFF_ROLES = ["inventory_staff", "blood_bank_manager", "system_admin"]


@router.get("", response_model=List[schemas.InventoryOut])
def list_inventory(
    blood_bank_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*STAFF_ROLES)),
):
    q = db.query(models.Inventory)
    if blood_bank_id:
        q = q.filter(models.Inventory.blood_bank_id == blood_bank_id)
    return q.all()


@router.get("/transactions", response_model=List[schemas.InventoryTransactionOut])
def list_recent_transactions(
    blood_bank_id: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*STAFF_ROLES)),
):
    """Most recent stock movements, newest first — for the inventory staff activity feed."""
    q = db.query(models.InventoryTransaction).join(models.Inventory)
    if blood_bank_id:
        q = q.filter(models.Inventory.blood_bank_id == blood_bank_id)
    rows = q.order_by(models.InventoryTransaction.created_at.desc()).limit(limit).all()
    return [
        schemas.InventoryTransactionOut(
            id=t.id,
            blood_group=t.inventory.blood_group.value if hasattr(t.inventory.blood_group, "value") else t.inventory.blood_group,
            component=t.inventory.component,
            txn_type=t.txn_type,
            quantity_units=t.quantity_units,
            note=t.note,
            created_at=t.created_at,
        )
        for t in rows
    ]


@router.post("/transaction", response_model=schemas.InventoryOut)
def record_transaction(
    payload: schemas.InventoryTransactionIn,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("inventory_staff", "system_admin")),
):
    """
    Records a stock movement and updates the running closing stock:
        closing_stock = opening_stock + receipts - issues - expiry/discard
    """
    if payload.quantity_units <= 0:
        raise HTTPException(400, "quantity_units must be a positive number")

    inv = (
        db.query(models.Inventory)
        .filter(
            models.Inventory.blood_bank_id == payload.blood_bank_id,
            models.Inventory.blood_group == payload.blood_group,
            models.Inventory.component == payload.component,
        )
        .first()
    )
    if inv is None:
        inv = models.Inventory(
            blood_bank_id=payload.blood_bank_id,
            blood_group=payload.blood_group,
            component=payload.component,
            quantity_units=0,
        )
        db.add(inv)
        db.flush()

    if payload.txn_type == "receipt":
        inv.quantity_units += payload.quantity_units
    elif payload.txn_type in ("issue", "expiry", "discard"):
        if payload.quantity_units > inv.quantity_units:
            raise HTTPException(400, f"Cannot {payload.txn_type} {payload.quantity_units} units; only {inv.quantity_units} in stock")
        inv.quantity_units -= payload.quantity_units
    else:
        raise HTTPException(400, "txn_type must be one of: receipt, issue, expiry, discard")

    txn = models.InventoryTransaction(
        inventory_id=inv.id,
        txn_type=payload.txn_type,
        quantity_units=payload.quantity_units,
        note=payload.note,
    )
    db.add(txn)
    db.commit()
    db.refresh(inv)
    return inv
