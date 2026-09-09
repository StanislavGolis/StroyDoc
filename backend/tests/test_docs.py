"""Тесты пула документов (паспорта) и привязки к позициям."""

from tests.conftest import auth_headers
from tests.test_files import _make_pdf_spec

URL = "/api/v1/objects"
PDF = b"%PDF-1.7\n%passport scan\n" + b"z" * 2000


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


def test_upload_attach_flow(client, make_user, login):
    obj, headers, items = _prepared(client, make_user, login)
    assert len(items) == 2
    item_ids = [i["id"] for i in items]

    # загрузка паспорта
    doc = client.post(
        f"{URL}/{obj['id']}/docs",
        data={"doc_number": "ПС-2026-01", "doc_title": "Паспорт датчика ДПМ-2"},
        files={"file": ("pass.pdf", PDF, "application/pdf")},
        headers=headers,
    )
    assert doc.status_code == 201, doc.text
    doc_id = doc.json()["id"]
    assert doc.json()["doc_number"] == "ПС-2026-01"

    # привязка к двум позициям
    attach = client.post(
        f"{URL}/{obj['id']}/docs/{doc_id}/attach",
        json={"item_ids": item_ids},
        headers=headers,
    )
    assert attach.status_code == 200
    assert attach.json()["linked_items"] == 2

    # в списке позиций у обеих docs_count = 1
    items2 = client.get(f"{URL}/{obj['id']}/items", headers=headers).json()
    assert all(it["docs_count"] == 1 for it in items2)

    # список документов по позиции
    docs_of_item = client.get(
        f"{URL}/{obj['id']}/docs?item_id={item_ids[0]}", headers=headers
    ).json()
    assert [d["id"] for d in docs_of_item] == [doc_id]

    # детач одной
    detach = client.post(
        f"{URL}/{obj['id']}/docs/{doc_id}/detach",
        json={"item_ids": [item_ids[0]]},
        headers=headers,
    )
    assert detach.json()["linked_items"] == 1
    after = client.get(f"{URL}/{obj['id']}/items", headers=headers).json()
    by_id = {it["id"]: it for it in after}
    assert by_id[item_ids[0]]["docs_count"] == 0
    assert by_id[item_ids[1]]["docs_count"] == 1

    # дубль загрузки того же файла — 409
    dup = client.post(
        f"{URL}/{obj['id']}/docs",
        files={"file": ("pass.pdf", PDF, "application/pdf")},
        headers=headers,
    )
    assert dup.status_code == 409

    # удаление документа
    resp = client.delete(f"{URL}/{obj['id']}/docs/{doc_id}", headers=headers)
    assert resp.status_code == 204
    left = client.get(f"{URL}/{obj['id']}/docs", headers=headers).json()
    assert left == []


def test_docs_only_pdf(client, make_user, login):
    obj, headers, _ = _prepared(client, make_user, login)
    bad = client.post(
        f"{URL}/{obj['id']}/docs",
        files={"file": ("doc.txt", b"hello", "text/plain")},
        headers=headers,
    )
    assert bad.status_code == 400


def test_reparse_cleans_previous_items(client, make_user, login):
    """PO-10: повторный парсинг перезаписывает позиции и корректно отвязывает документы."""
    obj, headers, items = _prepared(client, make_user, login)
    files = client.get(f"{URL}/{obj['id']}/files", headers=headers).json()
    file_id = files[0]["id"]

    doc = client.post(
        f"{URL}/{obj['id']}/docs",
        files={"file": ("pass.pdf", b"%PDF-1.7\npass" * 100, "application/pdf")},
        headers=headers,
    ).json()
    client.post(
        f"{URL}/{obj['id']}/docs/{doc['id']}/attach",
        json={"item_ids": [items[0]["id"]]},
        headers=headers,
    )

    rep = client.post(f"{URL}/{obj['id']}/files/{file_id}/parse", headers=headers)
    assert rep.status_code == 200
    assert rep.json()["parsed_items"] == 2

    after = client.get(f"{URL}/{obj['id']}/items", headers=headers).json()
    assert len(after) == 2  # старых позиций не осталось

    docs_after = client.get(f"{URL}/{obj['id']}/docs", headers=headers).json()
    assert len(docs_after) == 1
    assert docs_after[0]["linked_items"] == 0


def test_attach_rejects_foreign_item(client, make_user, login):
    obj, headers, items = _prepared(client, make_user, login)
    client.post(URL, json={"name": "Чужой"}, headers=headers)
    doc = client.post(
        f"{URL}/{obj['id']}/docs",
        files={"file": ("pass.pdf", PDF, "application/pdf")},
        headers=headers,
    ).json()

    resp = client.post(
        f"{URL}/{obj['id']}/docs/{doc['id']}/attach",
        json={"item_ids": [999_999]},
        headers=headers,
    )
    assert resp.status_code == 400
