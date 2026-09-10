"""Парсер PDF-спецификаций из рабочей документации.

Стратегия MVP: PDF с текстовым слоем и отрисованной сеткой таблицы.
- строки и столбцы определяются по линиям сетки (drawings);
- слова раскладываются по ячейкам через координаты (page.get_text("words"));
- строки с номером позиции и наименованием становятся записями SourceItem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf

JUNK_TOKENS = {
    "click",
    "to",
    "buy",
    "now",
    "pdf",
    "xchange",
    "editor",
    "tracker-software.com",
    "www.tracker-software.com",
    "pdf-xchange",
}


@dataclass
class PageTable:
    """Таблица страницы: колонки и строки со словами по ячейкам."""

    columns: list[float] = field(default_factory=list)
    rows: list[list[list[tuple[str, float, float, float, float]]]] = field(default_factory=list)


def _is_junk_word(word: str) -> bool:
    w = word.strip().lower().rstrip(".,!?")
    return w in JUNK_TOKENS


def _clean_word_list(words: list[tuple]) -> list[tuple]:
    """Удаляет слова водяного знака PDF-XChange и явный мусор."""
    result = []
    for w in words:
        if _is_junk_word(w[4]):
            continue
        result.append(w)
    return result


def _vlines(drawings: list, page_h: float) -> list[float]:
    """Вертикальные линии сетки (x-координаты)."""
    xs: set[float] = set()
    for d in drawings:
        rect = d.get("rect")
        if rect is None:
            continue
        if rect.width < 2 and rect.height > page_h * 0.35:
            xs.add(round(rect.x0, 1))
            xs.add(round(rect.x1, 1))
    return sorted(xs)


def _hlines(drawings: list, page_h: float) -> list[float]:
    """Горизонтальные линии сетки (y-координаты)."""
    ys: set[float] = set()
    for d in drawings:
        rect = d.get("rect")
        if rect is None:
            continue
        if rect.height < 2 and rect.width > 0.25 * page_h:
            ys.add(round(rect.y0, 1))
            ys.add(round(rect.y1, 1))
    return sorted(ys)

def _cell_of(columns: list[float], x_center: float) -> int:
    """Ячейка = интервал между соседними вертикальными линиями."""
    for i in range(len(columns) - 1):
        if columns[i] <= x_center <= columns[i + 1]:
            return i
    return 0 if x_center <= columns[0] else len(columns) - 2


def _extract_page_table(page: pymupdf.Page) -> PageTable:
    ph = page.rect.height
    drawings = list(page.get_drawings())
    columns = _vlines(drawings, ph)
    hlines = _hlines(drawings, ph)
    if len(columns) < 3 or len(hlines) < 2:
        return PageTable()

    cell_count = len(columns) - 1
    words = _clean_word_list(page.get_text("words"))
    rows: list[list[list[tuple[str, float, float, float, float]]]] = []
    for i in range(len(hlines) - 1):
        y_top, y_bot = hlines[i], hlines[i + 1]
        band_words = [w for w in words if y_top <= w[1] and w[3] <= y_bot]
        cells: list[list[tuple[str, float, float, float, float]]] = [[] for _ in range(cell_count)]
        for w in band_words:
            idx = _cell_of(columns, (w[0] + w[2]) / 2)
            cells[idx].append(w)
        rows.append(cells)
    return PageTable(columns=columns, rows=rows)


def _join(cell_words: list[tuple]) -> str:
    """Собирает слова ячейки в строку (слова упорядочены по x)."""
    ordered = sorted(cell_words, key=lambda w: (round(w[1], 1), w[0]))
    text = " ".join(w[4] for w in ordered)
    text = text.replace("\u00ad", "")  # мягкие переносы из вёрстки
    return re.sub(r"\s+", " ", text).strip()


_HEADER_HINTS: dict[str, str] = {
    "поз": "position",
    "наименование": "name",
    "тип": "mark_doc",
    "марка": "mark_doc",
    "код": "product_code",
    "поставщик": "supplier",
    "ед": "unit",
    "кол": "quantity",
    "масса": "mass",
    "примечания": "notes",
}


def _detect_header_mapping(header_cells: list[str]) -> dict[int, str]:
    """Определяет соответствие «индекс колонки -> поле» по строке заголовка."""
    mapping: dict[int, str] = {}
    for idx, cell in enumerate(header_cells):
        low = cell.lower()
        if "наименование" in low:
            mapping[idx] = "name"
            continue
        for hint, fname in _HEADER_HINTS.items():
            if hint in low and idx not in mapping:
                mapping[idx] = fname
                break
    return mapping

def _is_data_row(cells: list[str], mapping: dict[int, str]) -> bool:
    joined = "".join(cells).strip()
    if not joined:
        return False
    name_col = next((i for i, f in mapping.items() if f == "name"), None)
    if name_col is None or not cells[name_col].strip():
        return False
    # строка-заголовок (шапка повторяется на страницах) не должна попасть в данные
    return not ("наименование" in joined.lower() and "кол" in joined.lower())


def _to_decimal(text: str) -> float | None:
    clean = text.replace(" ", "").replace(",", ".").replace("\u00a0", "")
    if not clean or not re.fullmatch(r"\d+(\.\d+)?", clean):
        return None
    try:
        return float(clean)
    except ValueError:
        return None


def _parse_work_page(page: pymupdf.Page) -> list[dict]:
    """Парсинг листа «Ведомость объемов работ».

    В такой ведомости нет колонки «Поз.»: позиция = блок текста, который
    заканчивается значением количества в правой колонке. Каждый такой блок
    становится записью типа «работа».
    """
    words = _clean_word_list(page.get_text("words"))
    if not words:
        return []
    qx: float | None = None
    hy: float | None = None
    ex: float | None = None
    for w in sorted(words, key=lambda x: (x[1], x[0])):
        low = w[4].lower()
        if qx is None and low.startswith("кол") and ("-во" in low or "кол." == low):
            qx = w[0]
            hy = round(w[1], 1)
            continue
        if hy is not None and ex is None and low.rstrip(".") == "ед":
            if abs(w[1] - hy) <= 6:
                ex = w[0]
    if qx is None:
        return []
    if ex is None:
        ex = qx - 180

    num_re = re.compile(r"^\d{1,6}([.,]\d{1,3})?$")
    anchors: list[dict] = []
    for w in words:
        if (
            num_re.match(w[4])
            and abs((w[0] + w[2]) / 2 - qx) <= 140
            and (hy is None or w[1] > hy + 2)
        ):
            anchors.append({"y": w[1], "q": w[4].replace(",", ".")})
    anchors.sort(key=lambda a: a["y"])

    results: list[dict] = []
    for idx, a in enumerate(anchors):
        prev_y = anchors[idx - 1]["y"] if idx else (hy or 0) + 2
        # текст наименования — слова левее колонки «Ед.»
        name_tokens = [
            t[4]
            for t in words
            if t[1] >= prev_y - 2 and t[1] <= a["y"] + 1 and t[0] < (ex or 0)
        ]
        # единица измерения — слово между «Ед.» и количеством, ближайшее к количеству
        unit_tokens = [
            t
            for t in words
            if t[1] >= a["y"] - 14
            and t[1] <= a["y"] + 1
            and t[2] > (ex or 0)
            and t[0] < qx
            and not num_re.match(t[4])
        ]
        unit = max(unit_tokens, key=lambda t: t[1])[4] if unit_tokens else None
        name = " ".join(name_tokens)
        name = re.sub(r"\s+", " ", name).strip()
        name = name.replace(f" {a['q']}", "").strip()
        if name:
            results.append(
                {
                    "position": None,
                    "name": name,
                    "mark_doc": None,
                    "unit": unit,
                    "quantity": a["q"],
                    "notes": None,
                }
            )
    return results


FIELD_ORDER = [
    "position",
    "name",
    "mark_doc",
    "product_code",
    "supplier",
    "unit",
    "quantity",
    "mass",
    "notes",
]

# Метки колонок, по которым восстанавливаем разметку без линий сетки
_ANCHOR_LABELS = [
    ("position", lambda w: w == "поз." or w == "поз"),
    ("name", lambda w: w.startswith("наименован")),
    ("mark_doc", lambda w: w == "тип," or w == "тип"),
    ("product_code", lambda w: w == "код" or w == "код продукции"),
    ("supplier", lambda w: w == "поставщик"),
    ("unit", lambda w: w == "ед." or w == "ед"),
    ("quantity", lambda w: w == "кол." or w == "кол"),
    ("mass", lambda w: w == "масса"),
    ("notes", lambda w: w == "примечания" or w == "примечан"),
]

_POS_RE = re.compile(r"^\d{1,5}$|^\d{1,4}[а-яa-z]$|^[IVXLCDM]{1,6}$")

# Полный шифр листа: token вида «00819.РП.0.000.0-ТСО.СО1» (без пробелов, заканчивается .СО\d+)
_FULL_CODE_RE = re.compile(r"(?:^|\s)([^\s]*\.СО\d+)")


def _page_meta(text: str) -> tuple[str | None, str | None, bool]:
    """Мета страницы: полный шифр, категория поставки, признак «ведомости работ»."""
    full_code: str | None = None
    for m in _FULL_CODE_RE.finditer(text):
        candidate = m.group(1).strip().strip(".,;")
        # отбрасываем ложные срабатывания (короткий мусор без букв)
        if len(candidate) >= 5 and any(ch.isalpha() for ch in candidate):
            full_code = candidate
            break
    category: str | None = None
    low = text.lower()
    if "обменн" in low:
        category = "Обменный фонд"
    elif "подрядчик" in low:
        category = "Поставка подрядчика"
    elif "заказчик" in low:
        category = "Поставка заказчика"
    is_work = ("ведомост" in low and "работ" in low) or ("ведомост" in low and "объем" in low)
    return full_code, category, is_work


# --- Тип позиции (материал / оборудование / работа) -------------------------
# Лист спецификации определяет тип («Спецификация оборудования», «… материалов»).
# Если заголовок не распознан — словарный fallback по наименованию/марке.

_EQUIPMENT_HINTS = (
    "оборудован",
    "устройств",
    "прибор",
    "датчик",
    "извещател",
    "оповещател",
    "шкаф",
    "щит",
    "блок",
    "модул",
    "панел",
    "камер",
    "светильник",
    "прожектор",
    "кран",
    "насос",
    "вентилятор",
    "генератор",
    "трансформатор",
    "коммутатор",
    "регистратор",
    "контроллер",
    "сервер",
    "конвертер",
    "источник питания",
    "аккумулятор",
    "табло",
    "домофон",
)

_MATERIAL_HINTS = (
    "материал",
    "кабел",
    "провод",
    "труба",
    "гофр",
    "лоток",
    "крепеж",
    "муфт",
    "смесь",
    "бетон",
    "раствор",
    "грунтов",
    "краск",
    "эмаль",
    "лист",
    "уголок",
    "профил",
    "швеллер",
    "арматур",
    "сетка",
    "заглушк",
    "сва",
    "песок",
    "щебень",
    "гравий",
    "цемент",
    "оголовок",
    "фундамент",
    "кирпич",
    "блок газобетон",
    "изоляц",
    "герметик",
    "шпатлевк",
    "утеплител",
    "минват",
    "пенопласт",
    "битум",
    "рулон",
    "профнастил",
)



def _page_item_type(text: str, is_work: bool) -> str | None:
    """Тип позиций листа по заголовку: «work» / «equipment» / «material» / None.

    Стандартный заголовок ГОСТ «Спецификация оборудования, изделий и материалов»
    содержит оба слова — он неоднозначен, и тогда тип определяет словарь по строкам.
    """
    if is_work:
        return "work"
    head_lines = [line for line in text.splitlines() if line.strip()][:12]
    head = "\n".join(head_lines).lower()
    has_equipment = "оборудован" in head
    has_material = "материал" in head
    if has_equipment and not has_material:
        return "equipment"
    if has_material and not has_equipment:
        return "material"
    return None


def _row_item_type(rec: dict) -> str | None:
    """Словарный fallback: тип позиции по наименованию/марке/коду продукции."""
    text = " ".join(
        str(rec.get(key) or "") for key in ("name", "mark_doc", "product_code")
    ).lower()
    if not text.strip():
        return None
    for hint in _EQUIPMENT_HINTS:
        if hint in text:
            return "equipment"
    for hint in _MATERIAL_HINTS:
        if hint in text:
            return "material"
    return None


def _line_words(words: list[tuple], tol: float = 3.0) -> list[list[tuple]]:
    """Группирует слова в физические строки по координате y0."""
    ordered = sorted(words, key=lambda w: (w[1], w[0]))
    lines: list[list[tuple]] = []
    for w in ordered:
        if lines and abs(w[1] - lines[-1][0][1]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w[0]) for line in lines]


def _heuristic_page(page: pymupdf.Page) -> list[dict]:
    """Режим без сетки: колонки по словам-заголовкам, строки по базовым линиям."""
    words = _clean_word_list(page.get_text("words"))
    if not words:
        return []
    low = [(w[4].strip().lower().rstrip("."), w) for w in words]

    # 1) находим якорные метки колонок в верхней зоне страницы
    anchors: dict[str, tuple[float, float]] = {}
    for label, test in _ANCHOR_LABELS:
        for text, w in low:
            if w[1] < 160 and test(text):
                anchors[label] = (w[0], w[2])
                break
    if "position" not in anchors or "name" not in anchors:
        return []

    # 2) границы колонок — середины между стартовыми x якорей
    anchor_order = [f for f, _ in _ANCHOR_LABELS if f in anchors]
    starts = [anchors[f][0] for f in anchor_order]
    right = max((w[2] for _, w in low), default=page.rect.width)
    edges = [0.0] + [(starts[i] + starts[i + 1]) / 2 for i in range(len(starts) - 1)] + [right + 1]

    def col_idx(cx: float) -> int:
        for i in range(len(edges) - 1):
            if edges[i] <= cx <= edges[i + 1]:
                return i
        return len(anchor_order) - 1

    # 3) физические строки -> ячейки
    cell_lines: list[dict[int, str]] = []
    for line in _line_words(words):
        cells: dict[int, list[str]] = {}
        for w in line:
            idx = col_idx((w[0] + w[2]) / 2)
            cells.setdefault(idx, []).append(w[4])
        cell_lines.append({idx: " ".join(c).strip() for idx, c in cells.items()})

    # 4) сборка записей: строка начинается с номера позиции, продолжения добавляются в текущую
    results: list[dict] = []
    current: dict[str, str] | None = None

    def flush() -> None:
        nonlocal current
        if current and current.get("position") and current.get("name"):
            results.append(current)
        current = None

    for cl in cell_lines:
        # заголовок таблицы (его дублируют на каждой странице)
        if "наименование" in " ".join(cl.values()).lower():
            flush()
            continue
        # есть ли номер позиции в колонке "Поз."
        pos_value = next(
            (v for i, v in cl.items() if i < len(anchor_order) and anchor_order[i] == "position"),
            None,
        )

        if pos_value is not None and _POS_RE.match(pos_value.strip()):
            flush()
            current = {}
            current["position"] = pos_value.strip()
            for i, cell in cl.items():
                if i < len(anchor_order):
                    fname = anchor_order[i]
                    if fname != "position" and cell:
                        current[fname] = cell
            continue
        if current is not None:
            for i, cell in cl.items():
                if i < len(anchor_order):
                    fname = anchor_order[i]
                    if fname == "position" or not cell:
                        continue
                    current[fname] = (current.get(fname, "") + " " + cell).strip()
    flush()

    for r in results:
        r["quantity_value"] = _to_decimal(r["quantity"]) if r.get("quantity") else None
    return results


def parse_spec_pdf_bytes(data: bytes) -> list[dict]:
    """Возвращает список записей спецификации (dict с ключами FIELD_ORDER).

    На каждой странице сначала пробуется режим по сетке (колонки из линий),
    при нулевом результате — эвристический (колонки по словам-заголовкам).
    """
    doc = pymupdf.open(stream=data, filetype="pdf")
    results: list[dict] = []
    try:
        row_counter = 0

        def _store(recs: list[dict]) -> None:
            nonlocal row_counter
            for rec in recs:
                if not rec.get("position") and rec.get("item_type") != "work":
                    continue
                row_counter += 1
                rec["row_number"] = row_counter
                results.append(rec)

        for page_no, page in enumerate(doc, start=1):
            page_text = page.get_text()
            full_code, category, is_work = _page_meta(page_text)
            page_type = _page_item_type(page_text, is_work)
            page_records: list[dict] = []
            if is_work:
                page_records = _parse_work_page(page)
            else:
                table = _extract_page_table(page)
                if table.columns and table.rows:
                    # ищем строку-заголовок, чтобы понять раскладку колонок
                    mapping: dict[int, str] | None = None
                    header_idx = -1
                    for i, cells in enumerate(table.rows):
                        joined = [_join(c) for c in cells]
                        joined_text = " ".join(joined).lower()
                        if "наименование" in joined_text and any("поз" in c.lower() for c in joined):
                            mapping = _detect_header_mapping(joined)
                            header_idx = i
                            break
                    if mapping is not None:
                        for i, cells in enumerate(table.rows):
                            if i <= header_idx:
                                continue
                            joined = [_join(c) for c in cells]
                            if not _is_data_row(joined, mapping):
                                continue
                            rec: dict[str, str | float | None] = {f: None for f in FIELD_ORDER}
                            for idx, fname in mapping.items():
                                if 0 <= idx < len(joined):
                                    rec[fname] = joined[idx] or None
                            page_records.append(rec)
                if not page_records:
                    page_records = _heuristic_page(page)
            for rec in page_records:
                rec["quantity_value"] = _to_decimal(str(rec["quantity"])) if rec.get("quantity") else None
                rec["full_code"] = full_code
                rec["category"] = category
                rec["page_number"] = page_no
                rec["item_type"] = page_type or _row_item_type(rec)
            _store(page_records)
    finally:
        doc.close()
    return results


