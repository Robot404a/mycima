"""Business logic. Every function takes an open DB connection (`conn`) and runs plain SQL.

Concurrency rule: the unique index `uq_seat_active` on seat_claims is the single source of
truth. Two people claiming the same seat at the same moment -> Postgres lets exactly one
INSERT succeed and the other raises UniqueViolation, which we turn into a 409.
"""
import logging
import re

from fastapi import HTTPException
from psycopg import errors as pg_errors

import config
from movie_client import ShowtimeInfo

logger = logging.getLogger("reservation")


class SeatsUnavailable(Exception):
    def __init__(self, seats: list[str]):
        self.seats = seats


def _seat_key(label: str):
    m = re.match(r"^([A-Z]+)(\d+)$", label)
    return (len(m.group(1)), m.group(1), int(m.group(2))) if m else (99, label, 0)


def _sorted(seats) -> list[str]:
    return sorted(seats, key=_seat_key)


# A claim only counts as "taken" if it is booked, or held by a hold that has not expired yet.
_LIVE_CLAIM = "(sc.status = 'booked' OR (sc.status = 'held' AND h.expires_at > now()))"

_HOLD_STATUS = (
    "CASE WHEN h.status = 'active' AND h.expires_at <= now() THEN 'expired' ELSE h.status END"
)


# --------------------------------------------------------------------------- expiry
def expire_holds(conn, showtime_id: int | None = None) -> int:
    """Mark overdue holds as expired and free their seats. Safe to call at any time."""
    row = conn.execute(
        """
        WITH expired AS (
            UPDATE holds SET status = 'expired'
            WHERE id IN (
                SELECT id FROM holds
                WHERE status = 'active' AND expires_at <= now()
                  AND (%(sid)s::bigint IS NULL OR showtime_id = %(sid)s)
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id
        ),
        released AS (
            UPDATE seat_claims SET status = 'released'
            WHERE status = 'held' AND hold_id IN (SELECT id FROM expired)
            RETURNING id
        )
        SELECT (SELECT count(*) FROM expired) AS n
        """,
        {"sid": showtime_id},
    ).fetchone()
    return row["n"]


# --------------------------------------------------------------------------- seats
def taken_seats(conn, showtime_id: int) -> dict[str, dict]:
    rows = conn.execute(
        f"""
        SELECT sc.seat_label, sc.status, h.user_id
        FROM seat_claims sc JOIN holds h ON h.id = sc.hold_id
        WHERE sc.showtime_id = %s AND {_LIVE_CLAIM}
        """,
        (showtime_id,),
    ).fetchall()
    return {r["seat_label"]: {"status": r["status"], "user_id": r["user_id"]} for r in rows}


def seat_map(conn, info: ShowtimeInfo, user_id: int | None) -> dict:
    taken = taken_seats(conn, info.id)
    seats = []
    for row in info.rows:
        for number in range(1, info.seats_per_row + 1):
            label = f"{row}{number}"
            claim = taken.get(label)
            seats.append({
                "label": label,
                "row": row,
                "number": number,
                "status": "available" if claim is None else ("booked" if claim["status"] == "booked" else "held"),
                "mine": bool(claim and user_id is not None and claim["user_id"] == user_id),
            })
    return {
        "showtime_id": info.id,
        "price": float(info.price),
        "rows": list(info.rows),
        "seats_per_row": info.seats_per_row,
        "seats": seats,
    }


def counts_for(conn, showtime_ids: list[int]) -> dict[int, dict[str, int]]:
    rows = conn.execute(
        f"""
        SELECT sc.showtime_id, sc.status, count(*) AS n
        FROM seat_claims sc JOIN holds h ON h.id = sc.hold_id
        WHERE sc.showtime_id = ANY(%s) AND {_LIVE_CLAIM}
        GROUP BY sc.showtime_id, sc.status
        """,
        (showtime_ids,),
    ).fetchall()
    result = {sid: {"held": 0, "booked": 0} for sid in showtime_ids}
    for r in rows:
        result[r["showtime_id"]][r["status"]] = r["n"]
    return result


def availability(info: ShowtimeInfo, counts: dict[str, int]) -> dict:
    total = len(info.rows) * info.seats_per_row
    held, booked = counts["held"], counts["booked"]
    return {
        "showtime_id": info.id,
        "total": total,
        "available": total - held - booked,
        "held": held,
        "booked": booked,
    }


def suggest_seats(info: ShowtimeInfo, unavailable: set[str], count: int, limit: int = 3) -> list[dict]:
    """Best groups of `count` adjacent free seats: close to the middle of the hall, a bit behind the centre row."""
    center = (info.seats_per_row + 1) / 2
    target_row = (len(info.rows) - 1) * 0.6
    candidates = []
    for ri, row in enumerate(info.rows):
        for start in range(1, info.seats_per_row - count + 2):
            group = [f"{row}{n}" for n in range(start, start + count)]
            if any(s in unavailable for s in group):
                continue
            middle = start + (count - 1) / 2
            score = abs(middle - center) + 1.5 * abs(ri - target_row)
            candidates.append((score, ri, start, group, row))
    candidates.sort()
    chosen, used = [], set()
    for score, _, _, group, row in candidates:
        if used.intersection(group):
            continue  # don't offer overlapping suggestions
        chosen.append({"row": row, "seats": group, "score": round(score, 2)})
        used.update(group)
        if len(chosen) == limit:
            break
    return chosen


# --------------------------------------------------------------------------- holds
_HOLD_SQL = f"""
    SELECT h.id, h.user_id, h.showtime_id, {_HOLD_STATUS} AS status, h.created_at, h.expires_at,
           GREATEST(0, EXTRACT(EPOCH FROM (h.expires_at - now()))::int) AS seconds_left,
           COALESCE(array_agg(sc.seat_label) FILTER (WHERE sc.id IS NOT NULL), '{{}}') AS seats,
           COALESCE(sum(sc.price) FILTER (WHERE sc.id IS NOT NULL), 0) AS total
    FROM holds h LEFT JOIN seat_claims sc ON sc.hold_id = h.id
"""


def _hold_out(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "user_id": row["user_id"],
        "showtime_id": row["showtime_id"],
        "status": row["status"],
        "seats": _sorted(row["seats"]),
        "total": float(row["total"]),
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "seconds_left": row["seconds_left"] if row["status"] == "active" else 0,
    }


def get_hold(conn, hold_id, user_id: int | None = None) -> dict:
    row = conn.execute(_HOLD_SQL + " WHERE h.id = %s GROUP BY h.id", (hold_id,)).fetchone()
    if not row or (user_id is not None and row["user_id"] != user_id):
        raise HTTPException(404, "Hold not found.")
    return _hold_out(row)


def list_holds(conn, user_id=None, status=None, showtime_id=None, limit=50, offset=0) -> list[dict]:
    where, params = [], []
    if user_id is not None:
        where.append("h.user_id = %s"); params.append(user_id)
    if showtime_id is not None:
        where.append("h.showtime_id = %s"); params.append(showtime_id)
    if status:
        where.append(f"({_HOLD_STATUS}) = %s"); params.append(status)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        _HOLD_SQL + f" {clause} GROUP BY h.id ORDER BY h.created_at DESC LIMIT %s OFFSET %s",
        (*params, limit, offset),
    ).fetchall()
    return [_hold_out(r) for r in rows]


def create_hold(conn, user_id: int, info: ShowtimeInfo, labels: list[str]) -> dict:
    invalid = [s for s in labels if not info.has_seat(s)]
    if invalid:
        raise HTTPException(422, f"Seat(s) not in this hall: {', '.join(invalid)}")
    try:
        with conn.transaction():
            expire_holds(conn, info.id)
            # One active hold per user per showtime: picking seats again replaces the previous selection.
            conn.execute(
                """UPDATE seat_claims SET status = 'released'
                   WHERE status = 'held' AND hold_id IN (
                       SELECT id FROM holds WHERE user_id = %s AND showtime_id = %s AND status = 'active')""",
                (user_id, info.id),
            )
            conn.execute(
                "UPDATE holds SET status = 'released' WHERE user_id = %s AND showtime_id = %s AND status = 'active'",
                (user_id, info.id),
            )
            hold = conn.execute(
                """INSERT INTO holds (user_id, showtime_id, expires_at)
                   VALUES (%s, %s, now() + make_interval(secs => %s)) RETURNING id""",
                (user_id, info.id, config.HOLD_TTL_SECONDS),
            ).fetchone()
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO seat_claims (showtime_id, seat_label, hold_id, price) VALUES (%s, %s, %s, %s)",
                    [(info.id, label, hold["id"], info.price) for label in labels],
                )
    except pg_errors.UniqueViolation:
        rows = conn.execute(
            """SELECT seat_label FROM seat_claims
               WHERE showtime_id = %s AND seat_label = ANY(%s) AND status IN ('held', 'booked')""",
            (info.id, labels),
        ).fetchall()
        raise SeatsUnavailable(_sorted(r["seat_label"] for r in rows))
    return get_hold(conn, hold["id"])


def release_hold(conn, user_id: int, hold_id) -> dict:
    with conn.transaction():
        hold = conn.execute("SELECT user_id, status FROM holds WHERE id = %s FOR UPDATE", (hold_id,)).fetchone()
        if not hold or hold["user_id"] != user_id:
            raise HTTPException(404, "Hold not found.")
        if hold["status"] == "converted":
            raise HTTPException(409, "This hold is already a booking; cancel the booking instead.")
        if hold["status"] == "active":
            conn.execute("UPDATE holds SET status = 'released' WHERE id = %s", (hold_id,))
            conn.execute("UPDATE seat_claims SET status = 'released' WHERE hold_id = %s AND status = 'held'", (hold_id,))
    return get_hold(conn, hold_id, user_id)


# --------------------------------------------------------------------------- bookings
_BOOKING_SQL = """
    SELECT b.id, b.user_id, b.showtime_id, b.hold_id, b.status, b.total_amount, b.payment_ref,
           b.created_at, b.cancelled_at,
           COALESCE(array_agg(sc.seat_label) FILTER (WHERE sc.id IS NOT NULL), '{}') AS seats
    FROM bookings b LEFT JOIN seat_claims sc ON sc.booking_id = b.id
"""


def _booking_out(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "user_id": row["user_id"],
        "showtime_id": row["showtime_id"],
        "hold_id": str(row["hold_id"]) if row["hold_id"] else None,
        "status": row["status"],
        "seats": _sorted(row["seats"]),
        "total_amount": float(row["total_amount"]),
        "payment_ref": row["payment_ref"],
        "created_at": row["created_at"],
        "cancelled_at": row["cancelled_at"],
    }


def get_booking(conn, booking_id, user_id: int | None = None) -> dict:
    row = conn.execute(_BOOKING_SQL + " WHERE b.id = %s GROUP BY b.id", (booking_id,)).fetchone()
    if not row or (user_id is not None and row["user_id"] != user_id):
        raise HTTPException(404, "Booking not found.")
    return _booking_out(row)


def list_bookings(conn, user_id=None, status=None, showtime_id=None, limit=50, offset=0) -> list[dict]:
    where, params = [], []
    if user_id is not None:
        where.append("b.user_id = %s"); params.append(user_id)
    if status:
        where.append("b.status = %s"); params.append(status)
    if showtime_id is not None:
        where.append("b.showtime_id = %s"); params.append(showtime_id)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        _BOOKING_SQL + f" {clause} GROUP BY b.id ORDER BY b.created_at DESC LIMIT %s OFFSET %s",
        (*params, limit, offset),
    ).fetchall()
    return [_booking_out(r) for r in rows]


def confirm_hold(conn, user_id: int, hold_id, payment_ref: str | None) -> tuple[dict, bool]:
    """Turn a live hold into a booking. Returns (booking, created). Repeating the call is harmless."""
    expired = False
    booking_id = None
    with conn.transaction():
        hold = conn.execute(
            "SELECT user_id, showtime_id, status, expires_at <= now() AS overdue FROM holds WHERE id = %s FOR UPDATE",
            (hold_id,),
        ).fetchone()
        if not hold or hold["user_id"] != user_id:
            raise HTTPException(404, "Hold not found.")
        if hold["status"] == "converted":
            existing = conn.execute("SELECT id FROM bookings WHERE hold_id = %s", (hold_id,)).fetchone()
            return get_booking(conn, existing["id"], user_id), False
        if hold["status"] == "released":
            raise HTTPException(409, "This hold was released.")
        if hold["status"] == "expired" or hold["overdue"]:
            expire_holds(conn, hold["showtime_id"])
            expired = True  # raise AFTER the transaction so the expiry is saved
        else:
            total = conn.execute(
                "SELECT COALESCE(sum(price), 0) AS total FROM seat_claims WHERE hold_id = %s AND status = 'held'",
                (hold_id,),
            ).fetchone()["total"]
            booking_id = conn.execute(
                """INSERT INTO bookings (user_id, showtime_id, hold_id, total_amount, payment_ref)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (user_id, hold["showtime_id"], hold_id, total, payment_ref),
            ).fetchone()["id"]
            conn.execute(
                "UPDATE seat_claims SET status = 'booked', booking_id = %s WHERE hold_id = %s AND status = 'held'",
                (booking_id, hold_id),
            )
            conn.execute("UPDATE holds SET status = 'converted' WHERE id = %s", (hold_id,))
    if expired:
        raise HTTPException(410, "Your hold expired. Please select your seats again.")
    return get_booking(conn, booking_id, user_id), True


def cancel_booking(conn, booking_id, user_id: int | None = None) -> dict:
    """user_id=None means an administrator is cancelling."""
    with conn.transaction():
        booking = conn.execute("SELECT user_id, status FROM bookings WHERE id = %s FOR UPDATE", (booking_id,)).fetchone()
        if not booking or (user_id is not None and booking["user_id"] != user_id):
            raise HTTPException(404, "Booking not found.")
        if booking["status"] == "confirmed":
            conn.execute(
                "UPDATE bookings SET status = 'cancelled', cancelled_at = now() WHERE id = %s", (booking_id,)
            )
            conn.execute(
                "UPDATE seat_claims SET status = 'released' WHERE booking_id = %s AND status = 'booked'", (booking_id,)
            )
    return get_booking(conn, booking_id)


def after_booking_confirmed(booking: dict) -> None:
    """Single place to plug in the other services once their APIs are agreed
    (e.g. tell the Notification service to send the confirmation). Must never raise."""
    logger.info("booking confirmed id=%s user=%s seats=%s", booking["id"], booking["user_id"], booking["seats"])


# --------------------------------------------------------------------------- admin
def stats(conn) -> dict:
    totals = conn.execute(
        """
        SELECT
          (SELECT count(*) FROM bookings WHERE status = 'confirmed') AS confirmed_bookings,
          (SELECT count(*) FROM bookings WHERE status = 'cancelled') AS cancelled_bookings,
          (SELECT COALESCE(sum(total_amount), 0) FROM bookings WHERE status = 'confirmed') AS revenue,
          (SELECT count(*) FROM holds WHERE status = 'active' AND expires_at > now()) AS active_holds,
          (SELECT count(*) FROM seat_claims WHERE status = 'booked') AS seats_sold
        """
    ).fetchone()
    top = conn.execute(
        """SELECT showtime_id, count(*) AS seats_sold, COALESCE(sum(price), 0) AS revenue
           FROM seat_claims WHERE status = 'booked'
           GROUP BY showtime_id ORDER BY seats_sold DESC, showtime_id LIMIT 5"""
    ).fetchall()
    return {
        "confirmed_bookings": totals["confirmed_bookings"],
        "cancelled_bookings": totals["cancelled_bookings"],
        "revenue": float(totals["revenue"]),
        "active_holds": totals["active_holds"],
        "seats_sold": totals["seats_sold"],
        "top_showtimes": [
            {"showtime_id": r["showtime_id"], "seats_sold": r["seats_sold"], "revenue": float(r["revenue"])}
            for r in top
        ],
    }
