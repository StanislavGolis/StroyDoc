"""Тесты типа позиции и матрицы закрытия (Спринт 4).

Матрица заказчика: материал — паспорт/АВК/АОСР, оборудование — паспорт/АВК/ВСО,
работа — только ВР.
"""

from tests.conftest import auth_headers
from tests.test_files import _make_pdf_spec

URL = "/api/v1/objects"


def test_page_and_row_item_type() -> None:
    from app.parsing.spec_pdf import _page_item_type, _row_item_type

    assert _page_item_type("Ведомость объёмов работ. Шифр КЖ.СО2", True) == "work"
    assert (
        _page_item_type("Спецификация оборудования 00819.РП.0.000.0-ТСО.СО1", False)
        == "equipment"
    )
    assert _page_item_type("Спецификация материалов поставки подрядчика", False) == "material"
    assert _page_item_type("Шифр КЖ.СО2 Обменный фонд", False) is None

    assert _row_item_type({"name": "Датчик положения магнитогерконовый"}) == "equipment"
    assert _row_item_type({"name": "Кабель КВПЭФнг(А)-LS 2х2х0,9"}) == "material"
    assert _row_item_type({"name": "Монтаж щита управления"}) == "equipment"
    assert _row_item_type({"name": "Пусконаладочные работы"}) is None


def test_closure_matrix() -> None:
    from app.services.closure import act_covers, required_docs

    assert required_docs("material") == ["passport", "avk", "aosr"]
    assert required_docs("equipment") == ["passport", "avk", "vso"]
    assert required_docs("work") == ["vr"]
    # тип не определён — консервативно требуется паспорт и АВК
    assert required_docs(None) == ["passport", "avk"]

    assert act_covers("avk", "material") and act_covers("avk", "equipment")
    assert not act_covers("avk", "work")
    assert act_covers("aosr", "material") and not act_covers("aosr", "equipment")
    assert act_covers("vso", "equipment") and not act_covers("vso", "material")
    assert act_covers("vr", "work") and not act_covers("vr", "material")
    # неопределённый тип попадает в первичные документы, но не в ведомость работ
    assert act_covers("avk", None) and not act_covers("vr", None)


def _prepared(client, make_user, login):
    make_user("admin", email="a1@example.com")
    token = login("a1@example.com")
    headers = auth_headers(token)
    obj = client.post(URL, json={"name": "Объект"}, headers=headers).json()
    up = client.post(
        f"{URL}/{obj['id']}/files",
        data={"kind": "spec"},
        files={"file": ("spec.pdf", _make_pdf_spec(), "application/pdf")},
        headers=headers,
    ).json()
    client.post(f"{URL}/{obj['id']}/files/{up['id']}/parse", headers=headers)
    items = client.get(f"{URL}/{obj['id']}/items", headers=headers).json()
    assert len(items) == 2
    return obj, headers, items


def _set_type(client, obj, headers, item_id: int, value: str | None) -> dict:
    resp = client.patch(
        f"{URL}/{obj['id']}/items/{item_id}", json={"item_type": value}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_patch_item_type_and_filters(client, make_user, login) -> None:
    obj, headers, items = _prepared(client, make_user, login)

    # заголовка листа нет — тип определён словарём (датчик/извещатель → оборудование)
    assert items[0]["item_type"] == "equipment"
    assert items[0]["required_docs"] == ["passport", "avk", "vso"]

    first = _set_type(client, obj, headers, items[0]["id"], "material")
    assert first["item_type"] == "material"
    assert first["required_docs"] == ["passport", "avk", "aosr"]

    mat = client.get(f"{URL}/{obj['id']}/items?item_type=material", headers=headers).json()
    eq = client.get(f"{URL}/{obj['id']}/items?item_type=equipment", headers=headers).json()
    untyped = client.get(f"{URL}/{obj['id']}/items?untyped=true", headers=headers).json()
    assert [i["id"] for i in mat] == [items[0]["id"]]
    assert [i["id"] for i in eq] == [items[1]["id"]]
    assert untyped == []

    cleared = _set_type(client, obj, headers, items[0]["id"], None)
    assert cleared["item_type"] is None
    assert cleared["required_docs"] == ["passport", "avk"]
    untyped = client.get(f"{URL}/{obj['id']}/items?untyped=true", headers=headers).json()
    assert [i["id"] for i in untyped] == [items[0]["id"]]

    bad = client.patch(
        f"{URL}/{obj['id']}/items/{items[0]['id']}", json={"item_type": "foo"}, headers=headers
    )
    assert bad.status_code == 422


def test_set_type_bulk_only_untyped(client, make_user, login) -> None:
    obj, headers, items = _prepared(client, make_user, login)
    for it in items:
        _set_type(client, obj, headers, it["id"], None)

    resp = client.post(
        f"{URL}/{obj['id']}/items/set-type",
        json={"item_type": "material", "only_untyped": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] == 2

    mat = client.get(f"{URL}/{obj['id']}/items?item_type=material", headers=headers).json()
    assert len(mat) == 2


def test_act_type_matrix(client, make_user, login) -> None:
    obj, headers, items = _prepared(client, make_user, login)
    material_id, work_id = items[0]["id"], items[1]["id"]
    _set_type(client, obj, headers, material_id, "material")
    _set_type(client, obj, headers, work_id, "work")

    def create(act_type: str, ids: list[int]):
        return client.post(
            f"{URL}/{obj['id']}/acts",
            json={"act_type": act_type, "item_ids": ids},
            headers=headers,
        )

    assert create("avk", [material_id]).status_code == 201
    assert create("aosr", [material_id]).status_code == 201
    assert create("vso", [material_id]).status_code == 400  # ВСО — только оборудование
    assert create("vr", [material_id]).status_code == 400  # ВР — только работы
    assert create("avk", [work_id]).status_code == 400  # АВК — не работы
    assert create("vr", [work_id]).status_code == 201

    # позиция с неопределённым типом: АВК принимает, ВР — нет
    _set_type(client, obj, headers, material_id, None)
    assert create("avk", [material_id]).status_code == 201
    assert create("vr", [material_id]).status_code == 400

    # добавление несовместимой позиции в существующий акт тоже отклоняется
    act_id = create("vr", [work_id]).json()["id"]
    add = client.post(
        f"{URL}/{obj['id']}/acts/{act_id}/items",
        json={"item_ids": [material_id]},
        headers=headers,
    )
    assert add.status_code == 400


def test_dashboard_matrix(client, make_user, login) -> None:
    obj, headers, items = _prepared(client, make_user, login)
    material_id, work_id = items[0]["id"], items[1]["id"]
    _set_type(client, obj, headers, material_id, "material")
    _set_type(client, obj, headers, work_id, "work")

    doc = client.post(
        f"{URL}/{obj['id']}/docs",
        files={"file": ("pass.pdf", b"%PDF-1.7\nx" * 200, "application/pdf")},
        headers=headers,
    ).json()
    client.post(
        f"{URL}/{obj['id']}/docs/{doc['id']}/attach",
        json={"item_ids": [material_id]},
        headers=headers,
    )
    for act_type, item_id in (("avk", material_id), ("aosr", material_id), ("vr", work_id)):
        resp = client.post(
            f"{URL}/{obj['id']}/acts",
            json={"act_type": act_type, "item_ids": [item_id]},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text

    dash = next(
        o
        for o in client.get("/api/v1/dashboard/summary", headers=headers).json()["objects"]
        if o["object_id"] == obj["id"]
    )
    assert dash["material_total"] == 1
    assert dash["equipment_total"] == 0
    assert dash["untyped_total"] == 0
    assert dash["work_total"] == 1
    # паспорт нужен только материалу/оборудованию → знаменатель «без паспорта» равен 1
    assert dash["non_work_total"] == 1
    assert dash["items_with_docs"] == 1
    assert dash["items_without_docs"] == 0
    assert dash["avk_closed"] == 1
    assert dash["aosr_closed"] == 1
    assert dash["vso_closed"] == 0
    assert dash["vr_closed"] == 1

