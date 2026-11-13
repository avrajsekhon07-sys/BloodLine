"""Donor outreach notifications (FR-NOTE-1).

Alerts go ONLY to donors who pass the matching rules (compatible group,
available, consent given, cooldown cleared, optional radius). Withdrawing
consent stops future outreach because consent is checked at send time.
"""
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth, audit
from ..database import get_db
from ..services.donor_matching import match_donors
from ..services.geo import haversine_km
from ..services import push as push_svc

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/outreach", response_model=schemas.OutreachOut)
def send_outreach(
    payload: schemas.OutreachRequest,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("blood_bank_manager", "system_admin")),
):
    try:
        group = models.BloodGroup(payload.blood_group)
    except ValueError:
        raise HTTPException(400, "Unknown blood_group")
    bank = db.query(models.BloodBank).first()
    donors = db.query(models.Donor).all()
    dicts = [
        {
            "donor_id": d.id, "full_name": d.user.full_name, "blood_group": d.blood_group.value,
            "last_donation_date": d.last_donation_date, "is_available": d.is_available,
            "notification_consent": d.notification_consent,
            "distance_km": haversine_km(bank.latitude, bank.longitude, d.latitude, d.longitude) if bank else None,
        }
        for d in donors
    ]
    matches = match_donors(group.value, dicts, radius_km=payload.radius_km)

    message = payload.message or (
        f"{group.value} blood is running low{' at ' + bank.name if bank else ''}. If you are able to donate, "
        "please get in touch. Medical staff will confirm your eligibility at screening."
    )
    alert = (
        db.query(models.Alert).filter(models.Alert.blood_group == group).order_by(models.Alert.created_at.desc()).first()
    )
    since = datetime.utcnow() - timedelta(hours=24)
    notified = skipped = pushed = push_failed = no_sub = 0
    user_of = {d.id: d.user_id for d in donors}
    for m in matches:
        dup = (
            db.query(models.DonorNotification)
            .filter(models.DonorNotification.donor_id == m["donor_id"], models.DonorNotification.message == message, models.DonorNotification.sent_at >= since)
            .first()
        )
        if dup:
            skipped += 1
            continue
        db.add(models.DonorNotification(donor_id=m["donor_id"], alert_id=alert.id if alert else None, message=message))
        notified += 1
        if push_svc.configured() and db.query(models.PushSubscription).filter(models.PushSubscription.user_id == user_of[m["donor_id"]]).count() == 0:
            no_sub += 1  # this donor never enabled push on any browser (or the table was reset by a re-seed)
        ok, bad = push_svc.send_to_user(db, user_of[m["donor_id"]], "BloodLine", message)
        pushed += ok
        push_failed += bad
    audit.log(db, user.id, "outreach_sent", f"{group.value}: {notified} notified of {len(matches)} matched, {pushed} pushed")
    db.commit()
    return schemas.OutreachOut(matched=len(matches), notified=notified, skipped_recently_notified=skipped, pushed=pushed, push_failed=push_failed, push_no_subscription=no_sub)


@router.get("/me", response_model=List[schemas.NotificationOut])
def my_notifications(
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("donor")),
):
    if user.donor_profile is None:
        return []
    rows = (
        db.query(models.DonorNotification)
        .filter(models.DonorNotification.donor_id == user.donor_profile.id)
        .order_by(models.DonorNotification.sent_at.desc())
        .limit(50)
        .all()
    )
    return [schemas.NotificationOut(id=n.id, message=n.message, sent_at=n.sent_at, was_read=bool(n.was_read)) for n in rows]


@router.post("/{notification_id}/read", response_model=schemas.NotificationOut)
def mark_read(
    notification_id: str,
    db: Session = Depends(get_db),
    user: models.UserAccount = Depends(auth.require_roles("donor")),
):
    n = db.query(models.DonorNotification).filter(models.DonorNotification.id == notification_id).first()
    if n is None or user.donor_profile is None or n.donor_id != user.donor_profile.id:
        raise HTTPException(404, "Notification not found")
    n.was_read = True
    db.commit()
    return schemas.NotificationOut(id=n.id, message=n.message, sent_at=n.sent_at, was_read=True)
