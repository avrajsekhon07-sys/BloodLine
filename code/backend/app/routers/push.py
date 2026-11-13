"""Web Push subscription management for donors."""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, auth
from ..database import get_db
from ..services import push as push_svc

router = APIRouter(prefix="/push", tags=["push"])


class SubscribeIn(BaseModel):
    endpoint: str
    keys: dict  # {"p256dh": ..., "auth": ...}


@router.get("/public-key")
def public_key():
    if not push_svc.configured():
        raise HTTPException(503, "Push notifications are not configured on this server.")
    return {"public_key": os.environ["VAPID_PUBLIC_KEY"]}


@router.post("/subscribe", status_code=201)
def subscribe(payload: SubscribeIn, db: Session = Depends(get_db),
              user: models.UserAccount = Depends(auth.require_roles("donor"))):
    p256dh, auth_key = payload.keys.get("p256dh"), payload.keys.get("auth")
    if not p256dh or not auth_key:
        raise HTTPException(400, "keys.p256dh and keys.auth are required")
    sub = db.query(models.PushSubscription).filter(models.PushSubscription.endpoint == payload.endpoint).first()
    if sub is None:
        sub = models.PushSubscription(user_id=user.id, endpoint=payload.endpoint, p256dh=p256dh, auth=auth_key)
        db.add(sub)
    else:  # same browser re-subscribing (possibly under a different login)
        sub.user_id, sub.p256dh, sub.auth = user.id, p256dh, auth_key
    db.commit()
    return {"subscribed": True}


@router.post("/unsubscribe")
def unsubscribe(payload: SubscribeIn, db: Session = Depends(get_db),
                user: models.UserAccount = Depends(auth.require_roles("donor"))):
    db.query(models.PushSubscription).filter(
        models.PushSubscription.endpoint == payload.endpoint, models.PushSubscription.user_id == user.id
    ).delete()
    db.commit()
    return {"subscribed": False}
