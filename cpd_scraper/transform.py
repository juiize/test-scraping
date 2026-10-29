"""รวมตัวเลขตาม logic ของหน้าเว็บ และตรวจความสอดคล้องของผลรวม"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .config import SummarySpec

log = logging.getLogger(__name__)


class SchemaError(KeyError):
    """ไม่พบฟิลด์ที่คาดไว้ใน response (ชื่อฟิลด์อาจเปลี่ยน)"""

    def __str__(self) -> str:  # KeyError ใส่ quote ให้ข้อความ ทำให้อ่านยาก
        return str(self.args[0]) if self.args else ""


def to_int(value: Any) -> int:
    """แปลงค่าเป็น int: None -> 0, "1,234" -> 1234, 12.0 -> 12"""
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(round(value))
    text = str(value).replace(",", "").strip()
    try:
        return int(round(float(text)))
    except ValueError as exc:
        raise ValueError(f"แปลง {value!r} เป็นตัวเลขไม่ได้") from exc


def get_field(row: Mapping[str, Any], name: str) -> Any:
    """อ่านฟิลด์แบบไม่สนตัวพิมพ์ใหญ่/เล็ก (เผื่อ API ส่ง PascalCase เช่น DataM)"""
    if name in row:
        return row[name]
    lowered = name.lower()
    for key, value in row.items():
        if key.lower() == lowered:
            return value
    raise SchemaError(name)


def _has_field(rows: Iterable[Mapping[str, Any]], name: str) -> bool:
    lowered = name.lower()
    return any(k.lower() == lowered for row in rows for k in row)


def aggregate(spec: SummarySpec, rows: List[Mapping[str, Any]]) -> Dict[str, int]:
    """คืนค่า {metric: value} ตาม spec.aggregate

    - "last": ใช้แถวสุดท้าย (เหมือน loop เขียนทับใน home.component.ts)
    - "sum":  รวมทุกแถว
    """
    if not rows:
        log.warning("%s: response ว่าง ใส่ค่า 0 ทุกตัว", spec.name)
        return {metric: 0 for metric in spec.fields}

    missing = [f for f in spec.fields.values() if not _has_field(rows, f)]
    if missing:
        available = sorted({k for row in rows for k in row})
        raise SchemaError(
            f"{spec.name}: ไม่พบฟิลด์ {missing} ใน response "
            f"(ฟิลด์ที่มี: {available}) ให้แก้ fields ใน cpd_scraper/config.py"
        )

    if spec.aggregate == "last":
        row = rows[-1]
        return {metric: to_int(_get_or_none(row, f)) for metric, f in spec.fields.items()}

    if spec.aggregate == "sum":
        return {
            metric: sum(to_int(_get_or_none(row, f)) for row in rows)
            for metric, f in spec.fields.items()
        }

    raise ValueError(f"aggregate ไม่รู้จัก: {spec.aggregate}")


def _get_or_none(row: Mapping[str, Any], name: str) -> Optional[Any]:
    try:
        return get_field(row, name)
    except SchemaError:
        return None


def validate(category: str, values: Mapping[str, int]) -> List[str]:
    """ตรวจว่าส่วนย่อยรวมกันได้เท่ากับยอดรวม คืน list ของข้อความเตือน (ว่าง = ผ่าน)"""
    warnings: List[str] = []
    if category == "coop":
        parts = values.get("active", 0) + values.get("non_active", 0)
        label = "active + non_active"
    else:
        parts = values.get("male", 0) + values.get("female", 0)
        label = "male + female"
    total = values.get("total", 0)
    if parts != total:
        warnings.append(f"{category}: {label} = {parts:,} ไม่เท่ากับ total = {total:,}")
    return warnings


def flatten_row(row: Mapping[str, Any], prefix: str = "") -> Dict[str, Any]:
    """แปลง dict ซ้อนเป็นคอลัมน์ "a.b" และ list เป็น JSON string (เพื่อเขียน CSV ได้)"""
    flat: Dict[str, Any] = {}
    for key, value in row.items():
        name = f"{prefix}{key}"
        if isinstance(value, Mapping):
            flat.update(flatten_row(value, prefix=name + "."))
        elif isinstance(value, (list, tuple)):
            flat[name] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            flat[name] = ""
        else:
            flat[name] = value
    return flat
