"""Тесты загрузчика файлов и парсера PDF-спецификаций."""

import pymupdf
import pytest

from tests.conftest import auth_headers

FILES_URL = "/api/v1/objects"
PDF_SAMPLE = b"%PDF-1.7\n% test fake pdf body\n" + b"x" * 1000


def _find_cyrillic_font() -> str | None:
    import os

    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _make_pdf_spec() -> bytes:
    """Синтетическая PDF-спецификация с сеткой, как в реальных РД."""
    font_file = _find_cyrillic_font()
    doc = pymupdf.open()
    page = doc.new_page(width=700, height=400)
    vx = [50, 80, 320, 430, 480, 530, 560, 590, 620, 650]
    hy = [60, 90, 120, 150, 180, 210]
    for x in vx:
        page.draw_line((x, 60), (x, 210))
    for y in hy:
        page.draw_line((50, y), (650, y))

    def put(cell: int, band_top: float, text: str) -> None:
        rect = pymupdf.Rect(vx[cell] + 4, band_top + 3, vx[cell + 1] - 4, band_top + 26)
        kwargs: dict = {"fontsize": 8, "align": pymupdf.TEXT_ALIGN_CENTER}
        if font_file:
            kwargs["fontname"] = "F0"
            kwargs["fontfile"] = font_file
        page.insert_textbox(rect, text, **kwargs)

    headers = ["Поз.", "Наименование", "Тип, марка", "Код", "Поставщик", "Ед.", "Кол.", "Масса", "Примечания"]
    for i, h in enumerate(headers):
        put(i, 75, h)  # центр полосы 60..90
    # строки данных: центры полос 105, 135, 165
    put(0, 105, "1")
    put(1, 105, "Датчик положения магнитогерконовый")
    put(2, 105, "ДПМ2 исп 204")
    put(3, 105, "421836")
    put(4, 105, "ООО НПП Магнито-Контакт")
    put(5, 105, "шт")
    put(6, 105, "2")
    put(7, 105, "0,95")
    put(0, 135, "2")
    put(1, 135, "Извещатель охранный радиоволновой")
    put(2, 135, "АНТИРИС 5.8 20А 01")
    put(5, 135, "компл")
    put(6, 135, "3")
    return doc.tobytes()


@pytest.fixture
def object_and_tokens(client, make_user, login):
    make_user("admin", email="a1@example.com")
    admin_token = login("a1@example.com")
    resp = client.post(
        FILES_URL, json={"name": "Объект файлов"}, headers=auth_headers(admin_token)
    )
    assert resp.status_code == 201
    return resp.json(), admin_token


def _upload(client, token, obj, kind="spec", filename="spec.pdf", content=PDF_SAMPLE, ct="application/pdf"):
    return client.post(
        f"{FILES_URL}/{obj['id']}/files",
        data={"kind": kind},
        files={"file": (filename, content, ct)},
        headers=auth_headers(token),
    )


def test_upload_and_duplicate(client, object_and_tokens):
    obj, token = object_and_tokens
    resp = _upload(client, token, obj)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["kind"] == "spec"
    assert body["status"] == "uploaded"
    assert body["original_filename"] == "spec.pdf"
    assert body["size_bytes"] == len(PDF_SAMPLE)
    assert len(body["sha256"]) == 64
    assert body["uploader"]["email"] == "a1@example.com"

    dup = _upload(client, token, obj)
    assert dup.status_code == 409


def test_upload_wrong_format_for_kind(client, object_and_tokens):
    obj, token = object_and_tokens
    # Паспорта не принимают txt
    resp = _upload(client, token, obj, kind="passport", filename="doc.txt", content=b"hello")
    assert resp.status_code == 400


def test_upload_magic_mismatch(client, object_and_tokens):
    obj, token = object_and_tokens
    resp = _upload(client, token, obj, filename="spec.pdf", content=b"this is not a pdf at all")
    assert resp.status_code == 400


def test_list_and_delete(client, object_and_tokens):
    obj, token = object_and_tokens
    file_id = _upload(client, token, obj).json()["id"]

    resp = client.get(f"{FILES_URL}/{obj['id']}/files", headers=auth_headers(token))
    assert resp.status_code == 200
    assert [f["id"] for f in resp.json()] == [file_id]

    resp = client.delete(f"{FILES_URL}/{obj['id']}/files/{file_id}", headers=auth_headers(token))
    assert resp.status_code == 204
    resp = client.get(f"{FILES_URL}/{obj['id']}/files", headers=auth_headers(token))
    assert resp.json() == []


def test_engineer_without_access_cannot_upload(client, make_user, login, object_and_tokens):
    obj, admin_token = object_and_tokens
    make_user("pto_engineer", email="eng@example.com")
    eng_token = login("eng@example.com")
    resp = _upload(client, eng_token, obj)
    assert resp.status_code == 403


def test_parse_spec_pdf(client, object_and_tokens):
    obj, token = object_and_tokens
    spec = _make_pdf_spec()
    file_id = _upload(client, token, obj, filename="spec.pdf", content=spec).json()["id"]

    resp = client.post(f"{FILES_URL}/{obj['id']}/files/{file_id}/parse", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "done"
    assert body["parsed_items"] == 2

    items = client.get(
        f"{FILES_URL}/{obj['id']}/items?source_file={file_id}", headers=auth_headers(token)
    ).json()
    assert len(items) == 2
    first = items[0]
    assert first["position"] == "1"
    assert first["name"] == "Датчик положения магнитогерконовый"
    assert first["mark"] == "ДПМ2 исп 204"
    assert first["unit"] == "шт"
    assert float(first["quantity"]) == 2.0
    assert "BUY" not in " ".join(i["name"] for i in items)


def test_parse_only_spec_pdf(client, object_and_tokens):
    obj, token = object_and_tokens
    upload = _upload(client, token, obj, kind="passport", filename="doc.pdf", content=PDF_SAMPLE)
    file_id = upload.json()["id"]
    resp = client.post(f"{FILES_URL}/{obj['id']}/files/{file_id}/parse", headers=auth_headers(token))
    assert resp.status_code == 400
