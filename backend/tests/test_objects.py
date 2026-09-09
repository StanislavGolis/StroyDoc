"""Тесты объектов и назначений (изоляция доступа — ключевой сценарий Спринта 1)."""


from tests.conftest import auth_headers

URL = "/api/v1/objects"


def _create_object(client, token: str, name: str = "Объект №1", **extra) -> dict:
    payload = {"name": name, "code": "Ш-001", **extra}
    resp = client.post(URL, json=payload, headers=auth_headers(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _assign(client, token: str, object_id: int, user_id: int) -> None:
    resp = client.post(
        f"{URL}/{object_id}/assignments", json={"user_id": user_id}, headers=auth_headers(token)
    )
    assert resp.status_code == 201, resp.text


def test_manager_creates_object(client, make_user, login, company):
    make_user("admin", email="admin@example.com")
    token = login("admin@example.com")

    obj = _create_object(client, token, name="ЖК Солнечный")
    assert obj["company_id"] == company.id
    assert obj["code"] == "Ш-001"
    assert obj["status"] == "planning"

    resp = client.get(URL, headers=auth_headers(token))
    assert resp.status_code == 200
    assert [o["id"] for o in resp.json()] == [obj["id"]]


def test_engineer_sees_only_assigned_objects(client, make_user, login):
    make_user("admin", email="admin@example.com")
    engineer = make_user("pto_engineer", email="eng@example.com")
    admin_token = login("admin@example.com")
    eng_token = login("eng@example.com")

    assigned = _create_object(client, admin_token, name="Назначенный")
    not_assigned = _create_object(client, admin_token, name="Чужой")
    _assign(client, admin_token, assigned["id"], engineer.id)

    resp = client.get(URL, headers=auth_headers(eng_token))
    assert resp.status_code == 200
    ids = [o["id"] for o in resp.json()]
    assert assigned["id"] in ids
    assert not_assigned["id"] not in ids


def test_engineer_forbidden_from_foreign_object(client, make_user, login):
    make_user("admin", email="admin@example.com")
    make_user("pto_engineer", email="eng@example.com")
    admin_token = login("admin@example.com")
    eng_token = login("eng@example.com")

    obj = _create_object(client, admin_token)
    # Не назначенный инженер не может прочитать объект
    assert client.get(f"{URL}/{obj['id']}", headers=auth_headers(eng_token)).status_code == 403


def test_engineer_cannot_manage_objects(client, make_user, login):
    make_user("admin", email="admin@example.com")
    engineer = make_user("pto_engineer", email="eng@example.com")
    admin_token = login("admin@example.com")
    eng_token = login("eng@example.com")
    obj = _create_object(client, admin_token)

    assert client.post(URL, json={"name": "X"}, headers=auth_headers(eng_token)).status_code == 403
    assert (
        client.patch(f"{URL}/{obj['id']}", json={"name": "X"}, headers=auth_headers(eng_token)).status_code
        == 403
    )
    assert (
        client.post(
            f"{URL}/{obj['id']}/assignments",
            json={"user_id": engineer.id},
            headers=auth_headers(eng_token),
        ).status_code
        == 403
    )


def test_get_missing_object_404(client, make_user, login):
    make_user("admin", email="admin@example.com")
    token = login("admin@example.com")
    assert client.get(f"{URL}/999999", headers=auth_headers(token)).status_code == 404


def test_assignment_flow(client, make_user, login):
    make_user("admin", email="admin@example.com")
    engineer = make_user("pto_engineer", email="eng@example.com")
    admin_token = login("admin@example.com")
    eng_token = login("eng@example.com")
    obj = _create_object(client, admin_token)

    _assign(client, admin_token, obj["id"], engineer.id)

    # Инженер видит объект в списке и по id
    assert client.get(f"{URL}/{obj['id']}", headers=auth_headers(eng_token)).status_code == 200

    # Дубликат назначения — 409
    resp = client.post(
        f"{URL}/{obj['id']}/assignments",
        json={"user_id": engineer.id},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 409

    # Список назначений содержит инженера
    resp = client.get(f"{URL}/{obj['id']}/assignments", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert [a["user"]["id"] for a in resp.json()] == [engineer.id]

    # Снятие назначения → инженер теряет доступ
    resp = client.delete(
        f"{URL}/{obj['id']}/assignments/{engineer.id}", headers=auth_headers(admin_token)
    )
    assert resp.status_code == 204
    assert client.get(f"{URL}/{obj['id']}", headers=auth_headers(eng_token)).status_code == 403


def test_cannot_assign_head_or_admin(client, make_user, login):
    make_user("admin", email="admin@example.com")
    head = make_user("pto_head", email="head@example.com")
    admin_token = login("admin@example.com")
    obj = _create_object(client, admin_token)

    resp = client.post(
        f"{URL}/{obj['id']}/assignments",
        json={"user_id": head.id},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 400


def test_filter_and_search(client, make_user, login):
    make_user("admin", email="admin@example.com")
    token = login("admin@example.com")
    active = _create_object(client, token, name="Котельная", status="active")
    _create_object(client, token, name="ТРП", status="closed")

    resp = client.get(f"{URL}?status=active", headers=auth_headers(token))
    assert [o["id"] for o in resp.json()] == [active["id"]]

    resp = client.get(f"{URL}?q=Котельн", headers=auth_headers(token))
    assert [o["id"] for o in resp.json()] == [active["id"]]
