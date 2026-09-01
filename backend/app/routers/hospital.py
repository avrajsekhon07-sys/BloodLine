from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/hospital", tags=["hospital"])


def _resolve_hospital(db: Session, user: models.UserAccount) -> models.Hospital:
    hu = db.query(models.HospitalUser).filter(models.HospitalUser.user_id == user.id).first()
    if hu is None:
        raise HTTPException(400, "This account is not linked to a hospital.")
    return hu.hospital


def _to_out(req: models.BloodRequest) -> schemas.BloodRequestOut:
    return schemas.BloodRequestOut(
        id=req.id,
        hospital_id=req.hospital_id,
        hospital_name=req.hospital.name,
        blood_group=req.blood_group.value if hasattr(req.blood_group, "value") else req.blood_group,
        component=req.component,
        quantity_units=req.quantity_units,
        urgency=req.urgency,
        status=req.status,
        notes=req.notes,
        created_at=req.created_at,
    )


@router.post("/requests", response_model=schemas.BloodRequestOut)
def create_request(
    payload: schemas.BloodRequestCreate,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("hospital_coordinator", "system_admin")),
):
    if payload.quantity_units <= 0:
        raise HTTPException(400, "quantity_units must be a positive number")
    if payload.urgency not in ("routine", "urgent", "emergency"):
        raise HTTPException(400, "urgency must be one of: routine, urgent, emergency")

    hospital = _resolve_hospital(db, user)
    req = models.BloodRequest(
        hospital_id=hospital.id,
        blood_group=payload.blood_group,
        component=payload.component,
        quantity_units=payload.quantity_units,
        urgency=payload.urgency,
        notes=payload.notes,
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return _to_out(req)


@router.get("/requests", response_model=List[schemas.BloodRequestOut])
def list_own_requests(
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("hospital_coordinator", "system_admin")),
):
    hospital = _resolve_hospital(db, user)
    rows = (
        db.query(models.BloodRequest)
        .filter(models.BloodRequest.hospital_id == hospital.id)
        .order_by(models.BloodRequest.created_at.desc())
        .all()
    )
    return [_to_out(r) for r in rows]
