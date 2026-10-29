"""ดึงข้อมูลจากแต่ละ endpoint แล้วแปลงเป็น Record (1 metric = 1 record)"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config
from .client import CpdClient
from .config import EndpointSpec
from .transform import aggregate, validate

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Record:
    scraped_at: str
    data_year: str  # ว่างสำหรับ coop (endpoint ไม่รับปี)
    sector: str  # ชื่อภาคภาษาไทย
    category: str
    metric: str
    value: int
    endpoint: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "scraped_at": self.scraped_at,
            "data_year": self.data_year,
            "sector": self.sector,
            "category": self.category,
            "metric": self.metric,
            "value": self.value,
            "endpoint": self.endpoint,
        }


def build_params(spec: EndpointSpec, year: int, sector_code: str) -> Optional[Dict[str, str]]:
    """สร้าง query string แบบเดียวกับ callable.setPathParam / setPathParamSector"""
    if spec.sector_style is None:
        return None
    if spec.sector_style == "standard":
        sector = config.SECTOR_PARAM_STANDARD[sector_code]
    elif spec.sector_style == "non_sector":
        sector = config.SECTOR_PARAM_NON_SECTOR[sector_code]
    else:
        raise ValueError(f"sector_style ไม่รู้จัก: {spec.sector_style}")
    return {"year": str(year), "sector": sector}


def fetch_category(
    client: CpdClient,
    spec: EndpointSpec,
    year: int,
    sector_code: str,
    scraped_at: datetime,
    raw_dir: Optional[Path] = None,
) -> List[Record]:
    params = build_params(spec, year, sector_code)
    rows, url = client.post(spec.path, params=params)
    log.info("%-24s %d แถว  <- %s", spec.name, len(rows), url)

    if raw_dir is not None:
        save_raw(raw_dir, spec, year if spec.uses_year else None, sector_code, url, rows, scraped_at)

    values = aggregate(spec, rows)
    for msg in validate(spec.category, values):
        log.warning("ตรวจผลรวมไม่ผ่าน: %s (ปี %s, %s)", msg, year, config.SECTOR_LABELS[sector_code])

    data_year = str(year) if spec.uses_year else ""
    sector_label = config.SECTOR_LABELS[sector_code] if spec.uses_year else config.SECTOR_LABELS["0"]
    ts = scraped_at.isoformat(timespec="seconds")
    return [
        Record(ts, data_year, sector_label, spec.category, metric, value, spec.name)
        for metric, value in values.items()
    ]


def save_raw(
    raw_dir: Path,
    spec: EndpointSpec,
    year: Optional[int],
    sector_code: str,
    url: str,
    rows: List[Dict[str, Any]],
    scraped_at: datetime,
) -> Path:
    """เก็บ JSON ดิบไว้ตรวจสอบ / ใช้เป็น test fixture"""
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = scraped_at.strftime("%Y%m%d_%H%M%S")
    suffix = f"_{year}_s{sector_code}" if year is not None else ""
    path = raw_dir / f"{stamp}_{spec.name}{suffix}.json"
    payload = {"url": url, "scraped_at": scraped_at.isoformat(timespec="seconds"), "rows": rows}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
