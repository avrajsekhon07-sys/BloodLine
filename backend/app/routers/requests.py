from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db
from .hospital import _to_out

router = APIRouter(prefix="/requests", tags=["requests"])

MANAGER_ROLES = ["blood_bank_manager", "system_admin"]


@router.get("", response_model=List[schemas.BloodRequestOut])
def list_requests(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*MANAGER_ROLES)),
):
    q = db.query(models.BloodRequest)
    if status:
        q = q.filter(models.BloodRequest.status == status)
    rows = q.order_by(models.BloodRequest.created_at.desc()).all()
    return [_to_out(r) for r in rows]


@router.post("/{request_id}/approve", response_model=schemas.BloodRequestOut)
def approve_request(
    request_id: str,
    blood_bank_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*MANAGER_ROLES)),
):
    """
    Approves a request and attempts to auto-issue the units from inventory,
    demonstrating the integrated flow: Hospital request -> Manager approval
    -> Inventory issue -> Inventory updates.

    If stock is insufficient the request is still marked approved (so the
    manager can see it was actioned) but status becomes "pending" again
    with a note, rather than silently failing — the shortage-risk / donor
    matching workflow is how that gap gets closed.
    """
    req = db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()
    if req is None:
        raise HTTPException(404, "Request not found")
    if req.status != "pending":
        raise HTTPException(400, f"Request is already '{req.status}', cannot approve again")

    if blood_bank_id is None:
        bank = db.query(models.BloodBank).first()
        if bank is None:
            raise HTTPException(400, "No blood bank found — run the seed script first.")
        blood_bank_id = bank.id

    inv = (
        db.query(models.Inventory)
        .filter(
            models.Inventory.blood_bank_id == blood_bank_id,
            models.Inventory.blood_group == req.blood_group,
            models.Inventory.component == req.component,
        )
        .first()
    )
    available = inv.quantity_units if inv else 0

    if inv is not None and available >= req.quantity_units:
        inv.quantity_units -= req.quantity_units
        db.add(models.InventoryTransaction(
            inventory_id=inv.id,
            txn_type="issue",
            quantity_units=req.quantity_units,
            note=f"Auto-issued for approved hospital request {req.id}",
        ))
        req.status = "fulfilled"
    else:
        # Not enough stock to fulfil right now — approve intent is recorded
        # via the note, but keep it pending so the manager still sees it on
        # the pending list and can act after a donor drive / restock.
        req.notes = (req.notes + " " if req.notes else "") + \
            f"[Approved but insufficient stock: {available}/{req.quantity_units} available at approval time.]"

    db.commit()
    db.refresh(req)
    return _to_out(req)


@router.post("/{request_id}/reject", response_model=schemas.BloodRequestOut)
def reject_request(
    request_id: str,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles(*MANAGER_ROLES)),
):
    req = db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()
    if req is None:
        raise HTTPException(404, "Request not found")
    if req.status != "pending":
        raise HTTPException(400, f"Request is already '{req.status}', cannot reject")

    req.status = "rejected"
    db.commit()
    db.refresh(req)
    return _to_out(req)
