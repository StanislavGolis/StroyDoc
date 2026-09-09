"""Тесты актов (АВК/АОСР/ВСО/ВР) и генерации DOCX."""

from tests.conftest import auth_headers
from tests.test_files import _make_pdf_spec

URL = "/api/v1/objects"


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
    return obj, headers, items


def test_act_flow_and_docx(client, make_user, login):
    obj, headers, items = _prepared(client, make_user, login)
    ids = [i["id"] for i in items[:2]]

    act = client.post(
        f"{URL}/{obj['id']}/acts",
        json={"act_type": "avk", "doc_number": "АВК-1", "item_ids": ids},
        headers=headers,
    )
    assert act.status_code == 201, act.text
    act_id = act.json()["id"]
    assert act.json()["act_type"] == "avk"
    assert act.json()["linked_items"] == 2

    # статус → готов
    upd = client.patch(
        f"{URL}/{obj['id']}/acts/{act_id}", json={"status": "ready"}, headers=headers
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "ready"

    # позиции акта
    act_items = client.get(f"{URL}/{obj['id']}/acts/{act_id}/items", headers=headers).json()
    assert len(act_items) == 2

    # дубликат добавления не меняет счётчик
    add = client.post(
        f"{URL}/{obj['id']}/acts/{act_id}/items",
        json={"item_ids": [items[0]["id"]]},
        headers=headers,
    )
    assert add.json()["linked_items"] == 2

    # генерация docx
    gen = client.get(f"{URL}/{obj['id']}/acts/{act_id}/generate", headers=headers)
    assert gen.status_code == 200
    assert gen.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")
    assert len(gen.content) > 1000

    # удалить одну позицию и акт
    rem = client.post(
        f"{URL}/{obj['id']}/acts/{act_id}/items/remove",
        json={"item_ids": [items[1]["id"]]},
        headers=headers,
    )
    assert rem.json()["linked_items"] == 1

    resp = client.delete(f"{URL}/{obj['id']}/acts/{act_id}", headers=headers)
    assert resp.status_code == 204
    left = client.get(f"{URL}/{obj['id']}/acts", headers=headers).json()
    assert left == []


def test_act_requires_object_items(client, make_user, login):
    obj, headers, items = _prepared(client, make_user, login)
    act = client.post(
        f"{URL}/{obj['id']}/acts",
        json={"act_type": "aosr", "item_ids": [999_999]},
        headers=headers,
    )
    assert act.status_code == 201  # несуществующие просто игнорируются
    assert act.json()["linked_items"] == 0


def test_act_auto_number(client, make_user, login):
    obj, headers, items = _prepared(client, make_user, login)
    act = client.post(
        f"{URL}/{obj['id']}/acts",
        json={"act_type": "avk", "item_ids": [items[0]["id"]]},
        headers=headers,
    )
    assert act.status_code == 201, act.text
    assert act.json()["doc_number"] == "АВК-001"


def test_acts_filter_by_type(client, make_user, login):
    obj, headers, items = _prepared(client, make_user, login)
    client.post(
        f"{URL}/{obj['id']}/acts",
        json={"act_type": "avk", "item_ids": [items[0]["id"]]},
        headers=headers,
    )
    client.post(
        f"{URL}/{obj['id']}/acts",
        json={"act_type": "vso", "item_ids": [items[0]["id"]]},
        headers=headers,
    )
    avk = client.get(f"{URL}/{obj['id']}/acts?act_type=avk", headers=headers).json()
    vso = client.get(f"{URL}/{obj['id']}/acts?act_type=vso", headers=headers).json()
    assert len(avk) == 1 and avk[0]["act_type"] == "avk"
    assert len(vso) == 1 and vso[0]["act_type"] == "vso"
