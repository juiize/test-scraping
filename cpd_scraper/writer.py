"""เขียนไฟล์ CSV ทั้งหมด

ไฟล์ทุกไฟล์เป็น UTF-8 แบบมี BOM (ต้นไฟล์) เพื่อให้ Excel เปิดภาษาไทยได้ถูกต้อง
โหมดปกติคือ append ต่อท้ายไฟล์เดิม ใช้ --overwrite ถ้าต้องการเขียนทับ
"""
from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .config import WIDE_COLUMNS
from .extract import Record, SectionResult

SUMMARY_COLUMNS = ["scraped_at", "data_year", "sector", "category", "metric", "value", "endpoint"]
PAGE_LONG_COLUMNS = ["scraped_at", "section", "section_title", "data_year", "sector",
                     "request", "row_no", "field", "value"]
RUN_LOG_COLUMNS = ["scraped_at", "section", "endpoint", "data_year", "sector", "request",
                   "status", "rows", "url", "error"]
SECTION_META_COLUMNS = ["scraped_at", "data_year", "sector"]


# ---------------------------------------------------------------------
# ตัวช่วยพื้นฐาน
# ---------------------------------------------------------------------
def _open_for_write(path: Path, append: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not (append and path.exists() and path.stat().st_size > 0)
    if is_new:
        return open(path, "w", encoding="utf-8-sig", newline=""), True
    return open(path, "a", encoding="utf-8", newline=""), False


def _write_fixed(path: Path, columns: Sequence[str], rows: Iterable[Dict[str, Any]], append: bool) -> int:
    fh, is_new = _open_for_write(path, append)
    n = 0
    with fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns), restval="", extrasaction="ignore")
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)
            n += 1
    return n


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


# ---------------------------------------------------------------------
# summary (การ์ดสรุป)
# ---------------------------------------------------------------------
def write_long(records: Sequence[Record], path: Path, append: bool = True) -> int:
    return _write_fixed(path, SUMMARY_COLUMNS, (r.as_dict() for r in records), append)


def to_wide(records: Iterable[Record]) -> List[Dict[str, object]]:
    """1 แถวต่อ (data_year, sector) และเติมค่า coop (ไม่ขึ้นกับปี) ลงทุกแถว"""
    records = list(records)
    coop = {f"coop_{r.metric}": r.value for r in records if r.category == "coop"}
    scraped_at = records[0].scraped_at if records else ""

    groups: "OrderedDict[Tuple[str, str], Dict[str, object]]" = OrderedDict()
    for r in records:
        if r.category == "coop":
            continue
        key = (r.data_year, r.sector)
        row = groups.setdefault(key, {"scraped_at": r.scraped_at, "data_year": r.data_year, "sector": r.sector})
        row[f"{r.category}_{r.metric}"] = r.value

    if not groups and coop:  # มีแต่ข้อมูล coop
        groups[("", "")] = {"scraped_at": scraped_at, "data_year": "", "sector": ""}

    rows = []
    for row in groups.values():
        row.update(coop)
        rows.append(row)
    return rows


def write_wide(records: Sequence[Record], path: Path, append: bool = True) -> int:
    columns = ["scraped_at", "data_year", "sector"] + WIDE_COLUMNS
    return _write_fixed(path, columns, to_wide(records), append)


# ---------------------------------------------------------------------
# ราย section (ทุกฟิลด์ใน response)
# ---------------------------------------------------------------------
def write_section_csv(path: Path, rows: Sequence[Dict[str, Any]], append: bool = True) -> int:
    """เขียน 1 ไฟล์ต่อ section; ถ้ามีคอลัมน์ใหม่ (API เพิ่มฟิลด์) จะรวม header ให้อัตโนมัติ"""
    if not rows:
        return 0
    old_header: List[str] = []
    old_rows: List[Dict[str, str]] = []
    if append and path.exists() and path.stat().st_size > 0:
        old_header, old_rows = read_csv(path)

    header: List[str] = []
    for col in list(old_header) + [c for r in rows for c in r]:
        if col not in header:
            header.append(col)

    if old_rows and header == old_header:
        return _write_fixed(path, header, rows, append=True)

    # header เปลี่ยน (หรือไฟล์ใหม่) -> เขียนใหม่ทั้งไฟล์พร้อมข้อมูลเดิม
    _write_fixed(path, header, list(old_rows) + list(rows), append=False)
    return len(rows)


def write_sections(
    results: Sequence[SectionResult], out_dir: Path, scraped_at: str, append: bool = True
) -> Dict[str, int]:
    """เขียน data/sections/<key>.csv คืน {key: จำนวนแถวที่เขียน}"""
    grouped: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    for res in results:
        if res.ok:
            grouped.setdefault(res.section.key, []).extend(res.table_rows(scraped_at))
    counts = {}
    for key, rows in grouped.items():
        counts[key] = write_section_csv(out_dir / f"{key}.csv", rows, append=append)
    return counts


def iter_page_long(results: Sequence[SectionResult], scraped_at: str):
    """ทุกค่าบนหน้าในรูปแบบ 1 แถวต่อ 1 ค่า (section, row_no, field, value)"""
    for res in results:
        if not res.ok:
            continue
        for row in res.table_rows(scraped_at):
            row_no = row["row_no"]
            for fld, value in row.items():
                if fld in SECTION_META_COLUMNS or fld == "row_no" or fld.startswith("req_"):
                    continue
                yield {
                    "scraped_at": scraped_at,
                    "section": res.section.key,
                    "section_title": res.section.title,
                    "data_year": res.data_year,
                    "sector": res.sector,
                    "request": res.request_label,
                    "row_no": row_no,
                    "field": fld,
                    "value": value,
                }


def write_page_long(results: Sequence[SectionResult], path: Path, scraped_at: str, append: bool = True) -> int:
    return _write_fixed(path, PAGE_LONG_COLUMNS, iter_page_long(results, scraped_at), append)


def write_run_log(results: Sequence[SectionResult], path: Path, scraped_at: str, append: bool = True) -> int:
    rows = (
        {
            "scraped_at": scraped_at,
            "section": r.section.key,
            "endpoint": r.section.endpoint,
            "data_year": r.data_year,
            "sector": r.sector,
            "request": r.request_label,
            "status": "ok" if r.ok else "error",
            "rows": len(r.rows),
            "url": r.url,
            "error": r.error or "",
        }
        for r in results
    )
    return _write_fixed(path, RUN_LOG_COLUMNS, rows, append)
