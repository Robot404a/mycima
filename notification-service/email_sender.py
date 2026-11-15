"""Builds the email text and sends it over SMTP (Mailpit in dev, a real server in prod)."""
import logging
import smtplib
from email.message import EmailMessage
from typing import Any

import config

log = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Raised when the SMTP server could not deliver the message."""


_TEMPLATES = {
    "reservation_created": (
        "Your reservation is confirmed",
        "Hello,\n\n"
        "Your reservation {reference} is confirmed.\n\n"
        "Movie:  {movie_title}\n"
        "Time:   {showtime}\n"
        "Seats:  {seats}\n"
        "Total:  {total_price}\n\n"
        "Enjoy the movie!\nMyCima",
    ),
    "reservation_cancelled": (
        "Your reservation was cancelled",
        "Hello,\n\n"
        "Your reservation {reference} has been cancelled.\n\n"
        "Movie:  {movie_title}\n"
        "Time:   {showtime}\n"
        "Seats:  {seats}\n\n"
        "We hope to see you soon.\nMyCima",
    ),
}


def render_email(notification_type: str, reference_id: str | None, data: dict[str, Any]) -> tuple[str, str]:
    """Return (subject, body). Missing data fields become '-' instead of crashing."""
    subject, body = _TEMPLATES[notification_type]
    seats = data.get("seats")
    values = {
        "reference": f"#{reference_id}" if reference_id else "",
        "movie_title": data.get("movie_title") or "-",
        "showtime": data.get("showtime") or "-",
        "seats": ", ".join(map(str, seats)) if seats else "-",
        "total_price": data.get("total_price") or "-",
    }
    return subject, body.format(**values)


def send_email(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = config.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as smtp:
            if config.SMTP_USE_TLS:
                smtp.starttls()
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        log.warning("email to %s failed: %s", to, exc)
        raise EmailSendError(str(exc)) from exc