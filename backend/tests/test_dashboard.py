"""Тесты дашборда руководителя."""

from tests.conftest import auth_headers


def test_dashboard_manager_only(client, make_user, login):
    make_user("admin", email="a1@example.com")
    make_user("pto_engineer", email="eng@example.com")
    admin = login("a1@example.com")
    eng = login("eng@example.com")

    assert client.get("/api/v1/dashboard/summary", headers=auth_headers(eng)).status_code == 403

    resp = client.get("/api/v1/dashboard/summary", headers=auth_headers(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert "objects" in body and "totals" in body
    assert body["totals"]["objects_total"] >= 0


def test_dashboard_counts(client, make_user, login):
    from tests.test_files import _make_pdf_spec

    make_user("admin", email="a1@example.com")
    token = login("a1@example.com")
    headers = auth_headers(token)
    obj = client.post("/api/v1/objects", json={"name": "Объект"}, headers=headers).json()
    up = client.post(
        f"/api/v1/objects/{obj['id']}/files",
        data={"kind": "spec"},
        files={"file": ("spec.pdf", _make_pdf_spec(), "application/pdf")},
        headers=headers,
    ).json()
    client.post(f"/api/v1/objects/{obj['id']}/files/{up['id']}/parse", headers=headers)
    items = client.get(f"/api/v1/objects/{obj['id']}/items", headers=headers).json()
    doc = client.post(
        f"/api/v1/objects/{obj['id']}/docs",
        files={"file": ("pass.pdf", b"%PDF-1.7\nx" * 200, "application/pdf")},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/objects/{obj['id']}/docs/{doc['id']}/attach",
        json={"item_ids": [items[0]["id"]]},
        headers=headers,
    )

    resp = client.get("/api/v1/dashboard/summary", headers=headers).json()
    dash = next(o for o in resp["objects"] if o["object_id"] == obj["id"])
    assert dash["tracked_items"] == 2
    assert dash["items_with_docs"] == 1
    assert dash["items_without_docs"] == 1
