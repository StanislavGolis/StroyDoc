"""Демо-данные «рабочий момент». Запуск с хоста: cd backend && python seed_demo_data.py"""
# ruff: noqa: E501
from __future__ import annotations

import json
import sys
import urllib.request
import uuid
from datetime import date, timedelta
from pathlib import Path

BASE = "http://localhost:8000/api/v1"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
SPEC_FILES = ["Спецификация ТСО.pdf", "Спецификация КЖ.pdf", "Спецификация ЭМ.pdf"]
ADMIN = {"email": "admin@example.com", "password": "admin123"}

ENGINEERS = [
    ("Иванов Иван Петрович", "demo.pto1@stroydoc.ru"),
    ("Петрова Мария Сергеевна", "demo.pto2@stroydoc.ru"),
    ("Смирнов Алексей Николаевич", "demo.pto3@stroydoc.ru"),
]
# name, code, status, инженеры, грузить РД, профиль закрытия (avk,aosr,vso,vr)
OBJECTS = [
    ("Володино: реконструкция ИТСО", "00819-ИТСО", "active", [1, 2], True, (0.13, 0.07, 0.05, 0.20)),
    ('ЖК "Солнечный", корпус 2', "0247-К2-РД", "active", [1, 3], True, (0.30, 0.18, 0.12, 0.50)),
    ("АБК-3 на промплощадке", "0312-АБК-3", "active", [2, 3], True, (0.14, 0.06, 0.05, 0.22)),
    ("Цех №7, ремонт кровли", "0405-Ц7", "planning", [3], False, None),
]
DRAFT_SIZES = (8, 5, 4, 6)  # доп. «черновики» по типам avk/aosr/vso/vr


class DemoError(RuntimeError):
    pass


def _req(method: str, path: str, token: str | None = None, body=None) -> object:
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:400]
        raise DemoError(f"{method} {path} -> {exc.code}: {detail}") from exc


def _upload_spec(token: str, object_id: int, path: Path) -> dict:
    boundary = uuid.uuid4().hex
    raw = path.read_bytes()
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="kind"\r\n\r\nspec\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\nContent-Type: application/pdf\r\n\r\n'.encode(),
        raw,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    req = urllib.request.Request(f"{BASE}/objects/{object_id}/files", data=b"".join(parts), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        raise DemoError(f"upload {path.name} -> {exc.code}: {detail}") from exc


def _pick_even(ids: list[int], count: int) -> list[int]:
    if count <= 0 or not ids:
        return []
    n = len(ids)
    count = min(count, n)
    step = n / count
    return [ids[min(n - 1, round(i * step))] for i in range(count)]
def _acts_for_object(token: str, oid: int, profiles: tuple[float, float, float, float]) -> None:
    items = _req("GET", f"/objects/{oid}/items", token=token)
    assert isinstance(items, list)
    # Матрица закрытия: АВК — материалы+оборудование, АОСР — материалы,
    # ВСО — оборудование, ВР — работы. Не типизированные идут в первичные документы.
    by_type: dict[str | None, list[int]] = {}
    for it in items:
        by_type.setdefault(it.get("item_type"), []).append(int(it["id"]))
    material = by_type.get("material", [])
    equipment = by_type.get("equipment", [])
    untyped = by_type.get(None, [])
    works = by_type.get("work", [])
    non_work = [*material, *equipment, *untyped]
    if not non_work and not works:
        print(f"  нет позиций для актов ({oid})")
        return

    pools = (
        non_work,  # avk
        [*material, *untyped],  # aosr
        [*equipment, *untyped],  # vso
        works,  # vr
    )

    today = date.today()
    for act_type, pool, share, draft_size in zip(
        ("avk", "aosr", "vso", "vr"),
        pools,
        profiles,
        DRAFT_SIZES,
        strict=True,
    ):
        pool_sorted = sorted(pool)
        main_ids = _pick_even(pool_sorted, max(1, round(len(pool_sorted) * share)))
        if main_ids:
            doc_date = (today - timedelta(days=3 + int(share * 40))).isoformat()
            act = _req("POST", f"/objects/{oid}/acts", token=token, body={"act_type": act_type, "doc_date": doc_date, "item_ids": main_ids})
            assert isinstance(act, dict)
            _req("PATCH", f"/objects/{oid}/acts/{act['id']}", token=token, body={"status": "ready"})
            print(f"  {act_type}: готов на {len(main_ids)} поз.")
        draft_ids = _pick_even(pool_sorted, draft_size)
        if draft_ids:
            _req("POST", f"/objects/{oid}/acts", token=token, body={"act_type": act_type, "item_ids": draft_ids})
            print(f"  {act_type}: черновик на {len(draft_ids)} поз.")


def main() -> None:
    token = _req("POST", "/auth/login", body=ADMIN)["access_token"]  # type: ignore[index]

    users = _req("GET", "/users", token=token)  # type: ignore[arg-type]
    assert isinstance(users, list)
    by_email = {u["email"]: u for u in users}
    eng_ids: dict[int, int] = {}
    for n, (name, email) in enumerate(ENGINEERS, start=1):
        if email in by_email:
            eng_ids[n] = by_email[email]["id"]
            print(f"инженер уже есть: {name} (id={eng_ids[n]})")
            continue
        created = _req("POST", "/users", token=token, body={"email": email, "full_name": name, "role": "pto_engineer"})  # type: ignore[arg-type]
        assert isinstance(created, dict)
        eng_ids[n] = created["user"]["id"]
        print(f"создан инженер: {name} (id={eng_ids[n]}, пароль: {created['generated_password']})")

    objects = _req("GET", "/objects", token=token)  # type: ignore[arg-type]
    assert isinstance(objects, list)
    by_name = {o["name"]: o for o in objects}

    # если старый демо-объект назывался «Володино (демо)» — приводим к рабочему названию
    first = OBJECTS[0]
    if first[0] not in by_name:
        for cand_name, cand in by_name.items():
            if cand_name.lower().startswith("володино"):
                patched = _req(
                    "PATCH",
                    f"/objects/{cand['id']}",
                    token=token,
                    body={"name": first[0], "code": first[1], "status": first[2]},
                )
                assert isinstance(patched, dict)
                by_name[first[0]] = patched
                print(f"переименован объект: «{cand_name}» -> «{first[0]}» (id={patched['id']})")
                break

    for name, code, status, engs, upload, profiles in OBJECTS:
        obj = by_name.get(name)
        if obj is None:
            obj = _req("POST", "/objects", token=token, body={"name": name, "code": code, "status": status})  # type: ignore[arg-type]
            assert isinstance(obj, dict)
            print(f"создан объект: {name} (id={obj['id']})")
        else:
            print(f"объект уже есть: {name} (id={obj['id']})")
        oid = int(obj["id"])

        for en in engs:
            try:
                _req("POST", f"/objects/{oid}/assignments", token=token, body={"user_id": eng_ids[en]})  # type: ignore[arg-type]
            except DemoError as exc:
                if "409" not in str(exc):
                    raise

        if upload:
            files = _req("GET", f"/objects/{oid}/files?kind=spec", token=token)  # type: ignore[arg-type]
            assert isinstance(files, list)
            if any(int(f["parsed_items"]) > 0 for f in files):
                total = sum(int(f["parsed_items"]) for f in files)
                print(f"  РД уже разобрана ({total} поз.), пропускаю")
            else:
                for fname in SPEC_FILES:
                    src = DOCS_DIR / fname
                    if not src.exists():
                        print(f"  ! нет файла {src.name}", file=sys.stderr)
                        continue
                    fl = _upload_spec(token, oid, src)
                    parsed = _req("POST", f"/objects/{oid}/files/{fl['id']}/parse", token=token)  # type: ignore[arg-type]
                    assert isinstance(parsed, dict)
                    print(f"  {fname} -> {parsed.get('parsed_items')} поз.")

        if profiles:
            acts = _req("GET", f"/objects/{oid}/acts", token=token)  # type: ignore[arg-type]
            if isinstance(acts, list) and acts:
                print(f"  акты уже есть ({len(acts)} шт.), пропускаю генерацию")
            else:
                _acts_for_object(token, oid, profiles)

    # --- итог ---------------------------------------------------------------
    summary = _req("GET", "/dashboard/summary", token=token)
    assert isinstance(summary, dict)
    print("\nИтог (карточки дашборда):")
    for o in summary["objects"]:
        print(
            f"  {o['name']:<34} материал: {o['material_total']}, оборудование: {o['equipment_total']}, "
            f"не типизировано: {o['untyped_total']}, работы: {o['work_total']}\n"
            f"  {'':<34} закрыто: АВК {o['avk_closed']}, АОСР {o['aosr_closed']}, "
            f"ВСО {o['vso_closed']}, ВР {o['vr_closed']}"
        )


if __name__ == "__main__":
    main()

