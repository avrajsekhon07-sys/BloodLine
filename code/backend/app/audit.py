"""Tiny audit helper. Callers commit; this only stages the row so the log entry
is written in the same transaction as the action it describes."""
from . import models


def log(db, user_id, action: str, detail: str = None):
    db.add(models.AuditLog(user_id=user_id, action=action, detail=detail))
