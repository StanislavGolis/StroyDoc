"""Тесты рабочей области объекта — шифры РД (RdSection)."""

from tests.conftest import auth_headers

URL = "/api/v1/objects"


def test_sections_crud_and_file_attach(client, make_user, login):
    make_user("admin", email="a1@example.com")
    token = login("a1@example.com")
    obj = client.post(URL, json={"name": "Объект"}, headers=auth_headers(token)).json()

    headers = auth_headers(token)
    # создаём шифры
    tso = client.post(
        f"{URL}/{obj['id']}/sections",
        json={"code": "ТСО", "name": "Теплоснабжение", "sort_order": 1},
        headers=headers,
    )
    assert tso.status_code == 201
    em = client.post(
        f"{URL}/{obj['id']}/sections", json={"code": "ЭМ", "sort_order": 2}, headers=headers
    ).json()
    assert em["id"] != tso.json()["id"]

    # дубликат кода — 409
    assert (
        client.post(
            f"{URL}/{obj['id']}/sections", json={"code": "ТСО"}, headers=headers
        ).status_code
        == 409
    )

    # список сортирован
    sections = client.get(f"{URL}/{obj['id']}/sections", headers=headers).json()
    assert [s["code"] for s in sections] == ["ТСО", "ЭМ"]

    # загрузка файла в шифр ТСО
    pdf = b"%PDF-1.7\nx" * 10
    up = client.post(
        f"{URL}/{obj['id']}/files",
        data={"kind": "spec", "section_id": tso.json()["id"]},
        files={"file": ("spec.pdf", pdf, "application/pdf")},
        headers=headers,
    )
    assert up.status_code == 201
    assert up.json()["section"]["code"] == "ТСО"

    # перенос файла в ЭМ через PATCH
    moved = client.patch(
        f"{URL}/{obj['id']}/files/{up.json()['id']}",
        json={"section_id": em["id"]},
        headers=headers,
    )
    assert moved.status_code == 200
    assert moved.json()["section"]["code"] == "ЭМ"

    # удаление шифра с файлами — 409
    assert (
        client.delete(f"{URL}/{obj['id']}/sections/{em['id']}", headers=headers).status_code == 409
    )
    # отвязали файл -> шифр можно удалить
    client.patch(f"{URL}/{obj['id']}/files/{up.json()['id']}", json={"section_id": None}, headers=headers)
    assert client.delete(f"{URL}/{obj['id']}/sections/{em['id']}", headers=headers).status_code == 204


def test_engineer_cannot_create_section(client, make_user, login):
    make_user("admin", email="a1@example.com")
    make_user("pto_engineer", email="eng@example.com")
    admin_token = login("a1@example.com")
    eng_token = login("eng@example.com")
    obj = client.post(URL, json={"name": "Объект"}, headers=auth_headers(admin_token)).json()

    resp = client.post(
        f"{URL}/{obj['id']}/sections", json={"code": "КЖ"}, headers=auth_headers(eng_token)
    )
    assert resp.status_code == 403


def test_items_filter_by_section(client, make_user, login):
    """Позиции распарсенного файла наследуют шифр файла и фильтруются по нему."""
    from tests.test_files import _make_pdf_spec

    make_user("admin", email="a1@example.com")
    token = login("a1@example.com")
    headers = auth_headers(token)
    obj = client.post(URL, json={"name": "Объект"}, headers=headers).json()

    section = client.post(
        f"{URL}/{obj['id']}/sections", json={"code": "ЭМ"}, headers=headers
    ).json()
    spec = _make_pdf_spec()
    up = client.post(
        f"{URL}/{obj['id']}/files",
        data={"kind": "spec", "section_id": section["id"]},
        files={"file": ("spec.pdf", spec, "application/pdf")},
        headers=headers,
    ).json()
    parse = client.post(f"{URL}/{obj['id']}/files/{up['id']}/parse", headers=headers)
    assert parse.status_code == 200, parse.text
    assert parse.json()["parsed_items"] == 2

    items = client.get(
        f"{URL}/{obj['id']}/items?section={section['id']}", headers=headers
    ).json()
    assert len(items) == 2
    assert items[0]["section"]["code"] == "ЭМ"
