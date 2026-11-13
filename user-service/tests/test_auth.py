"""Functional tests for registration, login and profile endpoints."""

from __future__ import annotations

import uuid

from shared.auth import create_access_token


def test_health_reports_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["service"] == "user-service"


def test_register_returns_token_and_profile(client):
    email = f"register-{uuid.uuid4().hex[:10]}@mycima.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "secretpass1", "full_name": "New Person"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0
    assert body["user"] == {
        "id": body["user"]["id"],
        "email": email,
        "full_name": "New Person",
        "role": "user",
        "created_at": body["user"]["created_at"],
    }


def test_register_rejects_duplicate_email(client, user):
    response = client.post(
        "/auth/register",
        json={"email": user["email"], "password": "secretpass1", "full_name": "Clone"},
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_register_validates_password_length(client):
    response = client.post(
        "/auth/register",
        json={
            "email": f"short-{uuid.uuid4().hex[:8]}@mycima.com",
            "password": "short",
            "full_name": "Short Password",
        },
    )
    assert response.status_code == 422


def test_login_success_returns_fresh_token(client, user):
    response = client.post(
        "/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["id"] == user["id"]
    assert body["access_token"]


def test_login_rejects_wrong_password(client, user):
    response = client.post(
        "/auth/login",
        json={"email": user["email"], "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_me_requires_authentication(client):
    response = client.get("/users/me")
    assert response.status_code == 401


def test_me_returns_current_profile(client, user):
    response = client.get("/users/me", headers=user["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["email"] == user["email"]


def test_expired_token_is_rejected(client, user):
    expired = create_access_token(
        user_id=user["id"], email=user["email"], expires_minutes=-1
    )
    response = client.get("/users/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_update_profile(client, user):
    response = client.patch(
        "/users/me",
        headers=user["headers"],
        json={"full_name": "Updated Name", "password": "brand-new-pass"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == "Updated Name"

    login = client.post(
        "/auth/login",
        json={"email": user["email"], "password": "brand-new-pass"},
    )
    assert login.status_code == 200
