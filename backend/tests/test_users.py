"""Тесты управления пользователями и ролевых ограничений."""

from tests.conftest import auth_headers

URL = "/api/v1/users"


def test_engineer_cannot_list_users(client, make_user, login):
    make_user("pto_engineer", email="eng@example.com")
    token = login("eng@example.com")
    resp = client.get(URL, headers=auth_headers(token))
    assert resp.status_code == 403


def test_admin_creates_user_with_generated_password(client, make_user, login, company):
    make_user("admin", email="admin@example.com")
    token = login("admin@example.com")

    resp = client.post(
        URL,
        json={
            "email": "ivan@example.com",
            "full_name": "Иванов Иван",
            "role": "pto_engineer",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["role"] == "pto_engineer"
    assert body["user"]["company_id"] == company.id
    generated = body["generated_password"]
    assert len(generated) >= 12

    # Новый пользователь может войти со сгенерированным паролем
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "ivan@example.com", "password": generated},
    )
    assert login_resp.status_code == 200


def test_duplicate_email_conflict(client, make_user, login):
    make_user("admin", email="admin@example.com")
    make_user("pto_engineer", email="dup@example.com")
    token = login("admin@example.com")

    resp = client.post(
        URL,
        json={"email": "dup@example.com", "full_name": "Дубль", "role": "pto_engineer"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 409


def test_pto_head_cannot_create_admin(client, make_user, login):
    make_user("pto_head", email="head@example.com")
    token = login("head@example.com")

    resp = client.post(
        URL,
        json={"email": "newadmin@example.com", "full_name": "Админ", "role": "admin"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


def test_admin_updates_user_and_deactivates(client, make_user, login):
    make_user("admin", email="admin@example.com")
    target = make_user("pto_engineer", email="eng@example.com")
    token = login("admin@example.com")

    resp = client.patch(
        f"{URL}/{target.id}",
        json={"full_name": "Новое имя", "is_active": False},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Новое имя"
    assert resp.json()["is_active"] is False

    # Деактивированный не может войти
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "eng@example.com", "password": "pass1234"},
    )
    assert login_resp.status_code == 403


def test_reset_password_invalidates_refresh(client, make_user, login):
    make_user("admin", email="admin@example.com")
    engineer = make_user("pto_engineer", email="eng@example.com")
    token = login("admin@example.com")
    # Инженер логинится и получает refresh-cookie
    client.post("/api/v1/auth/login", json={"email": "eng@example.com", "password": "pass1234"})

    resp = client.post(f"{URL}/{engineer.id}/reset-password", headers=auth_headers(token))
    assert resp.status_code == 200
    new_password = resp.json()["generated_password"]

    # Старый refresh-токен инженера недействителен
    assert client.post("/api/v1/auth/refresh").status_code == 401
    # Старый пароль не работает, новый — работает
    assert client.post(
        "/api/v1/auth/login", json={"email": "eng@example.com", "password": "pass1234"}
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login", json={"email": "eng@example.com", "password": new_password}
    ).status_code == 200


def test_cannot_edit_own_role(client, make_user, login):
    make_user("admin", email="admin@example.com")
    token = login("admin@example.com")
    me = client.get("/api/v1/auth/me", headers=auth_headers(token)).json()

    resp = client.patch(
        f"{URL}/{me['id']}",
        json={"role": "pto_engineer"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
