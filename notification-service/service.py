"""Notification logic: store the email, send it, retry failures."""
import logging
from datetime import datetime, timezone

from fastapi import HTTPException

import config
import db
import email_sender
from schemas import NotificationCreate

log = logging.getLogger("notification-service.service")

# Public columns (the email body stays internal).
_COLUMNS = ("id, user_id, recipient_email, type, reference_id, subject, "
            "status, attempts, error, created_at, sent_at")


def _finish(notification_id: int, status: str, error: str | None) -> dict:
    sent_at = datetime.now(timezone.utc) if status == "sent" else None
    with db.get_conn() as conn:
        return conn.execute(
            f"UPDATE notifications SET status = %s, error = %s, sent_at = %s "
            f"WHERE id = %s RETURNING {_COLUMNS}",
            (status, error, sent_at, notification_id),
        ).fetchone()


def _deliver(row: dict) -> dict:
    """Send one already-claimed row. No DB connection is held while talking to SMTP."""
    try:
        email_sender.send_email(row["recipient_email"], row["subject"], row["body"])
    except email_sender.EmailSendError as exc:
        return _finish(row["id"], "failed", str(exc))
    return _finish(row["id"], "sent", None)


def create_notification(payload: NotificationCreate) -> dict:
    subject, body = email_sender.render_email(payload.type, payload.reference_id, payload.data)
    with db.get_conn() as conn:
        row = conn.execute(
            """INSERT INTO notifications
                   (user_id, recipient_email, type, reference_id, subject, body,
                    status, attempts, last_attempt_at)
               VALUES (%s, %s, %s, %s, %s, %s, 'pending', 1, now())
               ON CONFLICT (type, reference_id) WHERE reference_id IS NOT NULL DO NOTHING
               RETURNING *""",
            (payload.user_id, payload.recipient_email, payload.type,
             payload.reference_id, subject, body),
        ).fetchone()
        if row is None:  # same event already recorded: do not email twice
            return conn.execute(
                f"SELECT {_COLUMNS} FROM notifications WHERE type = %s AND reference_id = %s",
                (payload.type, payload.reference_id),
            ).fetchone()
    return _deliver(row)


def retry_failed(limit: int = 20) -> int:
    """Claim failed (or stuck 'pending') rows and try again. Safe with several replicas:
    SKIP LOCKED + flipping the status to 'pending' means two replicas never send the same row."""
    with db.get_conn() as conn:
        rows = conn.execute(
            """UPDATE notifications
                  SET status = 'pending', attempts = attempts + 1, last_attempt_at = now()
                WHERE id IN (
                    SELECT id FROM notifications
                     WHERE status IN ('failed', 'pending')
                       AND attempts < %s
                       AND COALESCE(last_attempt_at, created_at) < now() - make_interval(secs => %s)
                     ORDER BY created_at
                     LIMIT %s
                       FOR UPDATE SKIP LOCKED)
            RETURNING *""",
            (config.MAX_SEND_ATTEMPTS, float(config.RETRY_DELAY_SECONDS), limit),
        ).fetchall()
    for row in rows:
        _deliver(row)
    return len(rows)


def retry_one(notification_id: int) -> dict:
    """Admin: force another attempt for a failed notification (ignores the attempts limit)."""
    with db.get_conn() as conn:
        row = conn.execute(
            """UPDATE notifications
                  SET status = 'pending', attempts = attempts + 1, last_attempt_at = now()
                WHERE id = %s AND status = 'failed'
            RETURNING *""",
            (notification_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(409, "Notification not found, or it is not in 'failed' state.")
    return _deliver(row)


def list_notifications(conn, *, user_id: int | None = None, status: str | None = None,
                       limit: int = 50, offset: int = 0) -> list[dict]:
    clauses, params = [], []
    if user_id is not None:
        clauses.append("user_id = %s")
        params.append(user_id)
    if status is not None:
        clauses.append("status = %s")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return conn.execute(
        f"SELECT {_COLUMNS} FROM notifications {where} "
        f"ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
        (*params, limit, offset),
    ).fetchall()


def get_notification(conn, notification_id: int, user_id: int) -> dict:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM notifications WHERE id = %s AND user_id = %s",
        (notification_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Notification not found.")
    return row