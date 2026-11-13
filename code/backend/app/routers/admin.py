from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/summary", response_model=schemas.AdminSummaryOut)
def admin_summary(
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("system_admin")),
):
    users_by_role = {}
    for role in db.query(models.Role).all():
        count = db.query(models.UserAccount).filter(models.UserAccount.role_id == role.id).count()
        users_by_role[role.name.value] = count

    return schemas.AdminSummaryOut(
        total_users=db.query(models.UserAccount).count(),
        total_donors=db.query(models.Donor).count(),
        total_hospitals=db.query(models.Hospital).count(),
        total_blood_banks=db.query(models.BloodBank).count(),
        users_by_role=users_by_role,
    )


@router.get("/users", response_model=List[schemas.AdminUserOut])
def list_users(
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("system_admin")),
):
    users = db.query(models.UserAccount).order_by(models.UserAccount.full_name).all()
    return [
        schemas.AdminUserOut(
            id=u.id,
            full_name=u.full_name,
            email=u.email,
            role=u.role.name.value,
            is_active=u.is_active,
        )
        for u in users
    ]
