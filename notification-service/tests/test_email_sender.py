import smtplib

import pytest

import email_sender


def test_render_created_fills_the_template():
    subject, body = email_sender.render_email(
        "reservation_created", "42",
        {"movie_title": "Inception", "showtime": "Sat 20:30", "seats": ["A1", "A2"], "total_price": "16.00"},
    )
    assert subject == "Your reservation is confirmed"
    for expected in ("#42", "Inception", "Sat 20:30", "A1, A2", "16.00"):
        assert expected in body


def test_render_with_missing_data_does_not_crash():
    subject, body = email_sender.render_email("reservation_cancelled", None, {})
    assert "cancelled" in subject.lower()
    assert "-" in body


def test_send_email_wraps_smtp_errors(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(smtplib, "SMTP", boom)
    with pytest.raises(email_sender.EmailSendError):
        email_sender.send_email("a@example.com", "subject", "body")


def test_send_email_builds_the_message(monkeypatch):
    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            captured["host"] = host

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            captured["tls"] = True

        def login(self, user, password):
            captured["login"] = True

        def send_message(self, msg):
            captured["msg"] = msg

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    email_sender.send_email("user@example.com", "Hello", "Body text")
    msg = captured["msg"]
    assert msg["To"] == "user@example.com"
    assert msg["Subject"] == "Hello"
    assert "Body text" in msg.get_content()