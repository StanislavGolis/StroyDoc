"""Тесты: полный шифр с листа, редактирование позиции, признак отслеживания."""

from tests.conftest import auth_headers
from tests.test_files import _make_pdf_spec

URL = "/api/v1/objects"


def test_page_meta_detects_code_and_category():
    from app.parsing.spec_pdf import _page_meta

    code, cat, is_work = _page_meta(
        "Спецификация оборудования ... 00819.РП.0.000.0-ТСО.СО1 поставки Заказчика"
    )
    assert code == "00819.РП.0.000.0-ТСО.СО1"
    assert cat == "Поставка заказчика"
    assert is_work is False

    code2, cat2, work = _page_meta("Шифр КЖ.СО2 Ведомость объемов работ")
    assert code2 == "КЖ.СО2"
    assert cat2 is None
    assert work is True


def test_edit_item_and_tracked(client, make_user, login):
    make_user("admin", email="a1@example.com")
    token = login("a1@example.com")
    headers = auth_headers(token)
    obj = client.post(URL, json={"name": "Объект"}, headers=headers).json()

    up = client.post(
        f"{URL}/{obj['id']}/files",
        data={"kind": "spec"},
        files={"file": ("spec.pdf", _make_pdf_spec(), "application/pdf")},
        headers=headers,
    )
    file_id = up.json()["id"]
    parse = client.post(f"{URL}/{obj['id']}/files/{file_id}/parse", headers=headers)
    assert parse.status_code == 200
    assert parse.json()["parsed_items"] == 2

    items = client.get(f"{URL}/{obj['id']}/items", headers=headers).json()
    first = items[0]
    assert first["tracked"] is True

    # редактируем поле и отключаем отслеживание
    resp = client.patch(
        f"{URL}/{obj['id']}/items/{first['id']}",
        json={"mark": "ДПМ-2 исп 204", "full_code": "00819.РП.0.000.0-ТСО.СО1", "tracked": False},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mark"] == "ДПМ-2 исп 204"
    assert body["full_code"] == "00819.РП.0.000.0-ТСО.СО1"
    assert body["tracked"] is False

    # список с фильтром tracked=false содержит только эту строку
    untracked = client.get(f"{URL}/{obj['id']}/items?tracked=false", headers=headers).json()
    assert [i["id"] for i in untracked] == [first["id"]]

    # явная очистка поля (null) применяется
    clear = client.patch(
        f"{URL}/{obj['id']}/items/{first['id']}", json={"mark": None}, headers=headers
    )
    assert clear.status_code == 200
    assert clear.json()["mark"] is None

    # массовое включение обратно
    bulk = client.post(
        f"{URL}/{obj['id']}/items/set-tracked",
        json={"tracked": True, "ids": [first["id"]]},
        headers=headers,
    )
    assert bulk.status_code == 200
    assert bulk.json()["updated"] == 1


def test_bulk_untrack_by_section(client, make_user, login):
    make_user("admin", email="a1@example.com")
    token = login("a1@example.com")
    headers = auth_headers(token)
    obj = client.post(URL, json={"name": "Объект"}, headers=headers).json()
    section = client.post(
        f"{URL}/{obj['id']}/sections", json={"code": "КЖ.СО2"}, headers=headers
    ).json()

    up = client.post(
        f"{URL}/{obj['id']}/files",
        data={"kind": "spec", "section_id": section["id"]},
        files={"file": ("spec.pdf", _make_pdf_spec(), "application/pdf")},
        headers=headers,
    ).json()
    client.post(f"{URL}/{obj['id']}/files/{up['id']}/parse", headers=headers)

    all_items = client.get(f"{URL}/{obj['id']}/items", headers=headers).json()
    assert len(all_items) == 2

    bulk = client.post(
        f"{URL}/{obj['id']}/items/set-tracked",
        json={"tracked": False, "section_id": section["id"]},
        headers=headers,
    )
    assert bulk.status_code == 200
    assert bulk.json()["updated"] == 2

    untracked = client.get(
        f"{URL}/{obj['id']}/items?tracked=false&section={section['id']}", headers=headers
    ).json()
    assert len(untracked) == 2
