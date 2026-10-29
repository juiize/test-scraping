"""เขียน CSV แบบ long (หลัก) และ wide (เสริม)

ใช้ encoding utf-8-sig (มี BOM) เฉพาะตอนสร้างไฟล์ใหม่ เพื่อให้ Excel เปิดภาษาไทยได้
และเวลา append จะเขียนต่อแบบ utf-8 ธรรมดา (BOM ต้องมีแค่ต้นไฟล์)
"""
from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from .config import WIDE_COLUMNS
from .extract import Record

LONG_COLUMNS = ["scraped_at", "data_year", "sector", "category", "metric", "value", "endpoint"]


def _open_for_write(path: Path, append: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not (append and path.exists() and path.stat().st_size > 0)
    if is_new:
        return open(path, "w", encoding="utf-8-sig", newline=""), True
    return open(path, "a", encoding="utf-8", newline=""), False


def write_long(records: Sequence[Record], path: Path, append: bool = True) -> int:
    fh, is_new = _open_for_write(path, append)
    with fh:
        writer = csv.DictWriter(fh, fieldnames=LONG_COLUMNS)
        if is_new:
            writer.writeheader()
        for rec in records:
            writer.writerow(rec.as_dict())
    return len(records)


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
    rows = to_wide(records)
    fieldnames = ["scraped_at", "data_year", "sector"] + WIDE_COLUMNS
    fh, is_new = _open_for_write(path, append)
    with fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, restval="")
        if is_new:
            writer.writeheader()
        writer.writerows(rows)
    return len(rows)
