import pytest

import config
import email_sender
import service
from conftest import auth

INTERNAL = {"X-Internal-Token": "test-internal-key"}


def payload(**overrides) -> dict:
    body = {
        "user_id": 1,
        "recipient_email": "user@example.com",
        "type": "reservation_created",
        "reference_id": "booking-1",
        "data": {"movie_title": "Inception", "showtime": "Sat 20:30",
                 "seats": ["A1", "A2"], "total_price": "16.00"},
    }
    body.update(overrides)
    return body


def failing_sender(to, subject, body):
    raise email_sender.EmailSendError("smtp down")


@pytest.fixture
def outbox(monkeypatch):
    """Replace the real SMTP sender; every 'sent' email lands in this list."""
    sent = []
    monkeypatch.setattr(email_sender, "send_email",
                        lambda to, subject, body: sent.append({"to": to, "subject": subject, "body": body}))
    return sent


@pytest.fixture
def smtp_down(monkeypatch):
    monkeypatch.setattr(email_sender, "send_email", failing_sender)


# ---- health ------------------------------------------------------------------------------
def test_health_is_ok(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


# ---- POST /notifications (internal) ------------------------------------------------------
def test_create_requires_the_internal_key(client, outbox):
    assert client.post("/notifications", json=payload()).status_code == 403
    assert client.post("/notifications", json=payload(), headers={"X-Internal-Token": "wrong"}).status_code == 403
    assert client.post("/notifications", json=payload(), headers=auth(1)).status_code == 403  # a user token is not enough
    assert outbox == []


def test_create_sends_the_email(client, outbox):
    r = client.post("/notifications", json=payload(), headers=INTERNAL)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "sent" and body["attempts"] == 1 and body["sent_at"] is not None
    assert len(outbox) == 1 and outbox[0]["to"] == "user@example.com"
    assert "Inception" in outbox[0]["body"]


def test_smtp_failure_is_saved_as_failed_but_still_returns_201(client, smtp_down):
    r = client.post("/notifications", json=payload(), headers=INTERNAL)
    assert r.status_code == 201
    assert r.json()["status"] == "failed" and "smtp down" in r.json()["error"]


def test_same_event_twice_sends_only_one_email(client, outbox):
    first = client.post("/notifications", json=payload(), headers=INTERNAL).json()
    second = client.post("/notifications", json=payload(), headers=INTERNAL).json()
    assert first["id"] == second["id"]
    assert len(outbox) == 1


def test_created_and_cancelled_for_the_same_booking_are_both_sent(client, outbox):
    client.post("/notifications", json=payload(type="reservation_created"), headers=INTERNAL)
    client.post("/notifications", json=payload(type="reservation_cancelled"), headers=INTERNAL)
    assert len(outbox) == 2


def test_invalid_input_is_rejected(client, outbox):
    assert client.post("/notifications", json=payload(recipient_email="not-an-email"), headers=INTERNAL).status_code == 422
    assert client.post("/notifications", json=payload(type="spam"), headers=INTERNAL).status_code == 422
    assert outbox == []


# ---- user endpoints ----------------------------------------------------------------------
def test_user_endpoints_need_a_login(client):
    assert client.get("/notifications").status_code == 401


def test_user_only_sees_their_own_notifications(client, outbox):
    mine = client.post("/notifications", json=payload(user_id=1, reference_id="b1"), headers=INTERNAL).json()
    theirs = client.post("/notifications", json=payload(user_id=2, reference_id="b2"), headers=INTERNAL).json()

    listed = client.get("/notifications", headers=auth(1)).json()["notifications"]
    assert [n["id"] for n in listed] == [mine["id"]]
    assert client.get(f"/notifications/{mine['id']}", headers=auth(1)).status_code == 200
    assert client.get(f"/notifications/{theirs['id']}", headers=auth(1)).status_code == 404


# ---- admin endpoints ---------------------------------------------------------------------
def test_admin_endpoints_are_admin_only(client, outbox):
    client.post("/notifications", json=payload(user_id=1, reference_id="b1"), headers=INTERNAL)
    client.post("/notifications", json=payload(user_id=2, reference_id="b2"), headers=INTERNAL)

    assert client.get("/admin/notifications").status_code == 401
    assert client.get("/admin/notifications", headers=auth(1)).status_code == 403
    r = client.get("/admin/notifications", headers=auth(99, "admin"))
    assert r.status_code == 200 and len(r.json()["notifications"]) == 2


def test_admin_can_retry_a_failed_notification(client, monkeypatch):
    monkeypatch.setattr(email_sender, "send_email", failing_sender)
    failed = client.post("/notifications", json=payload(), headers=INTERNAL).json()
    assert failed["status"] == "failed"

    sent = []
    monkeypatch.setattr(email_sender, "send_email", lambda to, subject, body: sent.append(to))
    admin = auth(99, "admin")
    retried = client.post(f"/admin/notifications/{failed['id']}/retry", headers=admin)
    assert retried.status_code == 200
    assert retried.json()["status"] == "sent" and retried.json()["attempts"] == 2
    assert sent == ["user@example.com"]
    # already sent: cannot be retried again
    assert client.post(f"/admin/notifications/{failed['id']}/retry", headers=admin).status_code == 409


# ---- automatic retry ---------------------------------------------------------------------
def test_retry_loop_resends_failed_notifications(client, monkeypatch):
    monkeypatch.setattr(config, "RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr(email_sender, "send_email", failing_sender)
    failed = client.post("/notifications", json=payload(), headers=INTERNAL).json()
    assert failed["status"] == "failed"

    sent = []
    monkeypatch.setattr(email_sender, "send_email", lambda to, subject, body: sent.append(to))
    assert service.retry_failed() == 1
    assert sent == ["user@example.com"]
    row = client.get(f"/notifications/{failed['id']}", headers=auth(1)).json()
    assert row["status"] == "sent" and row["attempts"] == 2


def test_retry_loop_gives_up_after_max_attempts(client, monkeypatch):
    monkeypatch.setattr(config, "RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr(config, "MAX_SEND_ATTEMPTS", 1)
    monkeypatch.setattr(email_sender, "send_email", failing_sender)
    client.post("/notifications", json=payload(), headers=INTERNAL)
    assert service.retry_failed() == 0   # attempts (1) already reached the limit (1)