"""ดึงข้อมูลทุก section ของหน้าแรก และสร้างตัวเลขสรุป (summary)"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import config
from .client import ApiError, CpdClient
from .config import SectionSpec, SummarySpec
from .transform import SchemaError, aggregate, flatten_row, validate

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# โครงสร้างข้อมูล
# ---------------------------------------------------------------------
@dataclass
class SectionResult:
    """ผลการเรียก 1 request (1 section x 1 ปี x 1 ภาค x 1 body variant)"""

    section: SectionSpec
    year: Optional[int]  # None = section นี้ไม่รับปี
    sector_code: Optional[str]  # None = section นี้ไม่รับภาค
    variant: Dict[str, str] = field(default_factory=dict)
    url: str = ""
    rows: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def data_year(self) -> str:
        return "" if self.year is None else str(self.year)

    @property
    def sector(self) -> str:
        return "" if self.sector_code is None else config.SECTOR_LABELS[self.sector_code]

    @property
    def request_label(self) -> str:
        return "&".join(f"{k}={v}" for k, v in self.variant.items())

    def table_rows(self, scraped_at: str) -> List[Dict[str, Any]]:
        """แถวสำหรับ CSV ราย section: คอลัมน์ meta + ทุกฟิลด์ใน response"""
        out = []
        for i, row in enumerate(self.rows, start=1):
            meta: Dict[str, Any] = {
                "scraped_at": scraped_at,
                "data_year": self.data_year,
                "sector": self.sector,
            }
            for k, v in self.variant.items():
                meta[f"req_{k}"] = v
            meta["row_no"] = i
            meta.update(flatten_row(row))
            out.append(meta)
        return out


@dataclass(frozen=True)
class Record:
    """ตัวเลข 1 ค่าของการ์ดสรุป"""

    scraped_at: str
    data_year: str
    sector: str
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


# ---------------------------------------------------------------------
# query string / body
# ---------------------------------------------------------------------
def build_params(spec: SectionSpec, year: Optional[int], sector_code: Optional[str]) -> Optional[Dict[str, str]]:
    """สร้าง query string แบบเดียวกับ callable.setPathParam / setPathParamSector

    - year_key="year"        -> ?year=2568
    - year_key="year_change" -> ?year_change=2568   (setPathParam(URL, true))
    - sector_style="standard"   -> &sector=0|1|2
    - sector_style="non_sector" -> &sector=null|สหกรณ์ภาคการเกษตร|สหกรณ์นอกภาคการเกษตร
    """
    params: Dict[str, str] = {}
    if spec.year_key is not None:
        params[spec.year_key] = str(year)
    if spec.sector_style == "standard":
        params["sector"] = config.SECTOR_PARAM_STANDARD[sector_code or "0"]
    elif spec.sector_style == "non_sector":
        params["sector"] = config.SECTOR_PARAM_NON_SECTOR[sector_code or "0"]
    elif spec.sector_style is not None:
        raise ValueError(f"sector_style ไม่รู้จัก: {spec.sector_style}")
    return params or None


def build_body(variant: Dict[str, str]) -> Dict[str, str]:
    body = dict(config.DEFAULT_BODY)
    body.update(variant)
    return body


# ---------------------------------------------------------------------
# ดึงข้อมูล
# ---------------------------------------------------------------------
class PageFetcher:
    """เรียกทุก section ตามปี/ภาคที่ขอ โดยไม่เรียกซ้ำ request เดิม"""

    def __init__(self, client: CpdClient, scraped_at: datetime, raw_dir: Optional[Path] = None) -> None:
        self.client = client
        self.scraped_at = scraped_at
        self.raw_dir = raw_dir
        self._cache: Dict[Tuple, Tuple[List[Dict[str, Any]], str]] = {}

    def fetch_section(self, spec: SectionSpec, year: int, sector_code: str) -> List[SectionResult]:
        y = year if spec.uses_year else None
        s = sector_code if spec.uses_sector else None
        results = []
        for variant in spec.body_variants:
            res = SectionResult(spec, y, s, dict(variant))
            params = build_params(spec, y, s)
            body = build_body(variant)
            key = (spec.path, tuple(sorted((params or {}).items())), tuple(sorted(body.items())))
            try:
                if key not in self._cache:
                    self._cache[key] = self.client.post(spec.path, params=params, body=body)
                res.rows, res.url = self._cache[key]
                extra = f" [{res.request_label}]" if variant else ""
                log.info("%-32s %4d แถว  %s%s", spec.endpoint, len(res.rows), _when(res), extra)
                if self.raw_dir is not None:
                    save_raw(self.raw_dir, res, self.scraped_at)
            except ApiError as exc:
                res.error = str(exc)
                log.error("%s (%s): %s", spec.endpoint, _when(res), exc)
            results.append(res)
        return results

    def fetch_page(
        self,
        sections: Sequence[SectionSpec],
        years: Sequence[int],
        sector_codes: Sequence[str],
    ) -> List[SectionResult]:
        """ดึงทุก section; section ที่ไม่ขึ้นกับปี/ภาคจะเรียกแค่ครั้งเดียว"""
        done = set()
        results: List[SectionResult] = []
        for year in years:
            for sector in sector_codes:
                for spec in sections:
                    key = (
                        spec.key,
                        year if spec.uses_year else None,
                        sector if spec.uses_sector else None,
                    )
                    if key in done:
                        continue
                    done.add(key)
                    results.extend(self.fetch_section(spec, year, sector))
        return results


def _when(res: SectionResult) -> str:
    parts = []
    if res.year is not None:
        parts.append(f"ปี {res.year}")
    if res.sector_code is not None:
        parts.append(res.sector)
    return ", ".join(parts) or "ไม่ขึ้นกับปี/ภาค"


def save_raw(raw_dir: Path, res: SectionResult, scraped_at: datetime) -> Path:
    """เก็บ JSON ดิบไว้ตรวจสอบ / ใช้เป็น test fixture"""
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = scraped_at.strftime("%Y%m%d_%H%M%S")
    parts = [stamp, res.section.key]
    if res.year is not None:
        parts.append(str(res.year))
    if res.sector_code is not None:
        parts.append(f"s{res.sector_code}")
    parts += [f"{k}{v}" for k, v in res.variant.items()]
    path = raw_dir / ("_".join(parts) + ".json")
    payload = {
        "section": res.section.key,
        "url": res.url,
        "body": build_body(res.variant),
        "scraped_at": scraped_at.isoformat(timespec="seconds"),
        "rows": res.rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------
# สรุปตัวเลขบนการ์ด
# ---------------------------------------------------------------------
def build_summary(
    results: Iterable[SectionResult],
    scraped_at: datetime,
    summaries: Sequence[SummarySpec] = config.SUMMARIES,
) -> Tuple[List[Record], List[str]]:
    """คำนวณตัวเลขแบบเดียวกับหน้าเว็บจากผลที่ดึงมาแล้ว คืน (records, errors)"""
    ts = scraped_at.isoformat(timespec="seconds")
    by_section: Dict[str, List[SectionResult]] = {}
    for r in results:
        if r.ok:
            by_section.setdefault(r.section.key, []).append(r)

    records: List[Record] = []
    errors: List[str] = []
    for summ in summaries:
        for res in by_section.get(summ.section, []):
            try:
                values = aggregate(summ, res.rows)
            except (SchemaError, ValueError) as exc:
                errors.append(f"summary {summ.category} ({_when(res)}): {exc}")
                log.error(errors[-1])
                continue
            for msg in validate(summ.category, values):
                log.warning("ตรวจผลรวมไม่ผ่าน: %s (%s)", msg, _when(res))
            sector = res.sector or config.SECTOR_LABELS["0"]
            records.extend(
                Record(ts, res.data_year, sector, summ.category, metric, value, summ.name)
                for metric, value in values.items()
            )
    order = {s.category: i for i, s in enumerate(summaries)}
    records.sort(key=lambda r: (r.data_year != "", -int(r.data_year or 0), r.sector != "ทั้งหมด",
                                r.sector, order.get(r.category, 99)))
    return records, errors
