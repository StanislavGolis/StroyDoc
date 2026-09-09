"""Тесты авторизации: login, me, refresh, logout, деактивация."""

from tests.conftest import auth_headers


def test_login_success_returns_tokens_and_cookie(client, make_user, company):
    user = make_user("pto_engineer", email="engineer@example.com")
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "pass1234"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["id"] == user.id
    assert body["user"]["company_id"] == company.id
    assert body["user"]["email"] == user.email
    assert "stroydoc_refresh" in resp.cookies


def test_login_wrong_password(client, make_user):
    make_user("pto_engineer", email="engineer@example.com")
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "wrong-pass"},
    )
    assert resp.status_code == 401


def test_login_unknown_email(client):
    resp = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "pass1234"}
    )
    assert resp.status_code == 401


def test_login_inactive_user_blocked(client, make_user):
    make_user("pto_engineer", email="off@example.com", active=False)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "off@example.com", "password": "pass1234"},
    )
    assert resp.status_code == 403


def test_me_requires_token(client, make_user, login):
    make_user("pto_engineer", email="engineer@example.com")
    token = login("engineer@example.com")

    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth_headers("invalid.token.x")).status_code == 401

    resp = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "engineer@example.com"


def test_refresh_rotates_tokens(client, make_user):
    make_user("pto_engineer", email="engineer@example.com")
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "pass1234"},
    )
    assert login_resp.status_code == 200
    old_access = login_resp.json()["access_token"]

    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert resp.json()["access_token"]
    assert resp.json()["access_token"] != old_access
    assert "stroydoc_refresh" in resp.cookies


def test_refresh_without_cookie(client):
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


def test_logout_invalidates_refresh(client, make_user):
    make_user("pto_engineer", email="engineer@example.com")
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "pass1234"},
    ).json()["access_token"]

    resp = client.post("/api/v1/auth/logout", headers=auth_headers(token))
    assert resp.status_code == 204

    # Refresh-токен уже недействителен (token_version инкрементирована)
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
