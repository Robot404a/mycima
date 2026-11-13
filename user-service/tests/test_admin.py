"""Functional tests for the administrator endpoints."""

from __future__ import annotations


def test_admin_can_list_users(client, admin_headers):
    response = client.get("/admin/users", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 1
    assert body["limit"] == 50
    assert any(user["role"] == "admin" for user in body["items"])


def test_admin_can_search_users(client, admin_headers):
    response = client.get("/admin/users", headers=admin_headers, params={"q": "admin"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert all("admin" in user["email"] for user in body["items"])


def test_regular_user_cannot_list_users(client, user):
    response = client.get("/admin/users", headers=user["headers"])
    assert response.status_code == 403


def test_anonymous_cannot_list_users(client):
    response = client.get("/admin/users")
    assert response.status_code == 401


def test_admin_can_promote_a_user(client, admin_headers, user):
    response = client.patch(
        f"/admin/users/{user['id']}/role",
        headers=admin_headers,
        json={"role": "admin"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "admin"

    profile = client.get("/users/me", headers=user["headers"])
    assert profile.status_code == 200
    assert profile.json()["role"] == "admin"


def test_admin_unknown_user_returns_404(client, admin_headers):
    response = client.get("/admin/users/999999", headers=admin_headers)
    assert response.status_code == 404
