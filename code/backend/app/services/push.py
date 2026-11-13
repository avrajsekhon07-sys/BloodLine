"""Web Push delivery. Optional: needs `pywebpush` plus VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY
(generate with `python scripts/gen_vapid.py`). When not configured every call is a no-op and
in-app notifications still work."""
import json
import logging
import os

from .. import models

log = logging.getLogger("bloodline.push")


def configured() -> bool:
    return bool(os.getenv("VAPID_PUBLIC_KEY") and os.getenv("VAPID_PRIVATE_KEY"))


def send_to_user(db, user_id: str, title: str, body: str):
    """Returns (sent, failed). Failures are logged so a missing pop-up can be diagnosed from the server log."""
    if not configured():
        return 0, 0
    try:
        from pywebpush import WebPushException, webpush
    except Exception:
        log.warning("pywebpush is not installed; push disabled")
        return 0, 0
    sent = failed = 0
    for sub in db.query(models.PushSubscription).filter(models.PushSubscription.user_id == user_id).all():
        try:
            webpush(
                subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                data=json.dumps({"title": title, "body": body}),
                vapid_private_key=os.environ["VAPID_PRIVATE_KEY"],
                vapid_claims={"sub": os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")},  # fresh dict: the library mutates it
                ttl=3600,
            )
            sent += 1
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            log.warning("Web Push delivery failed (HTTP %s): %s", code, str(e)[:200])
            failed += 1
            if code in (404, 410):
                db.delete(sub)  # subscription expired or was revoked in the browser
        except Exception as e:
            log.warning("Web Push error: %s", str(e)[:200])
            failed += 1
    return sent, failed
