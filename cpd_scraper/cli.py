"""Command-line interface: python main.py --help"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

from . import config
from .client import ApiError, CpdClient, use_os_trust_store
from .extract import Record, fetch_category
from .transform import SchemaError
from .writer import write_long, write_wide

log = logging.getLogger("cpd_scraper")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    default_year = config.default_data_year()
    p = argparse.ArgumentParser(
        prog="python main.py",
        description="ดึงจำนวนสหกรณ์ / สมาชิก / กรรมการ / เจ้าหน้าที่ จาก bigdata.cpd.go.th แล้วบันทึกเป็น CSV",
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument("--year", type=int, default=default_year,
                   help=f"ปีข้อมูล (พ.ศ.) ค่าเริ่มต้น {default_year} เหมือนหน้าเว็บ")
    g.add_argument("--all-years", action="store_true",
                   help=f"ดึงทุกปีตั้งแต่ {config.FIRST_YEAR} ถึง {default_year}")
    p.add_argument("--sector", choices=["0", "1", "2", "all"], default="0",
                   help="0=ทั้งหมด (ค่าเริ่มต้น), 1=ภาคการเกษตร, 2=นอกภาคการเกษตร, all=ทั้ง 3 แบบ")
    p.add_argument("--out", type=Path, default=Path("data/cpd_summary.csv"),
                   help="ไฟล์ CSV แบบ long (ค่าเริ่มต้น data/cpd_summary.csv)")
    p.add_argument("--wide", action="store_true",
                   help="เขียนไฟล์แบบ wide เพิ่ม (<out>_wide.csv) 1 แถวต่อปีต่อภาค")
    p.add_argument("--overwrite", action="store_true",
                   help="เขียนทับไฟล์เดิม (ค่าเริ่มต้นคือ append ต่อท้าย)")
    p.add_argument("--save-raw", nargs="?", type=Path, const=Path("data/raw"), default=None,
                   metavar="DIR", help="เก็บ JSON ดิบของแต่ละ request (ค่าเริ่มต้น data/raw)")
    p.add_argument("--base-url", default=config.BASE_URL, help="base URL ของ API")
    p.add_argument("--timeout", type=float, default=30.0, help="timeout ต่อ request (วินาที)")
    p.add_argument("--delay", type=float, default=0.5, help="หน่วงระหว่าง request (วินาที)")
    p.add_argument("--ca-bundle", type=Path, default=None,
                   help="ไฟล์ CA (.pem) ของ proxy องค์กร กรณีเจอ SSL error")
    p.add_argument("-v", "--verbose", action="store_true", help="แสดง log ละเอียด")
    args = p.parse_args(argv)

    if args.all_years:
        args.years = list(range(default_year, config.FIRST_YEAR - 1, -1))
    else:
        args.years = [args.year]
    args.sectors = ["0", "1", "2"] if args.sector == "all" else [args.sector]
    return args


def run(args: argparse.Namespace, client: Optional[CpdClient] = None) -> int:
    if client is None:
        use_os_trust_store()
        client = CpdClient(
            base_url=args.base_url,
            timeout=args.timeout,
            delay=args.delay,
            verify=str(args.ca_bundle) if args.ca_bundle else True,
        )

    scraped_at = datetime.now(config.TZ_BANGKOK)
    records: List[Record] = []
    errors: List[str] = []

    def collect(spec: config.EndpointSpec, year: int, sector: str) -> None:
        try:
            records.extend(fetch_category(client, spec, year, sector, scraped_at, args.save_raw))
        except (ApiError, SchemaError, ValueError) as exc:
            msg = f"{spec.name} (ปี {year}, {config.SECTOR_LABELS[sector]}): {exc}"
            log.error(msg)
            errors.append(msg)

    # การ์ดจำนวนสหกรณ์ไม่ขึ้นกับปี/ภาค -> ดึงครั้งเดียว
    collect(config.ENDPOINTS_BY_CATEGORY["coop"], args.years[0], "0")

    for year in args.years:
        for sector in args.sectors:
            for spec in config.ENDPOINTS:
                if spec.uses_year:
                    collect(spec, year, sector)

    if not records:
        log.error("ไม่ได้ข้อมูลเลย ไม่ได้เขียนไฟล์")
        return 2

    append = not args.overwrite
    n = write_long(records, args.out, append=append)
    log.info("เขียน %d แถว -> %s", n, args.out)
    if args.wide:
        wide_path = args.out.with_name(args.out.stem + "_wide" + args.out.suffix)
        n = write_wide(records, wide_path, append=append)
        log.info("เขียน %d แถว -> %s", n, wide_path)

    print_summary(records)

    if errors:
        log.warning("มี %d request ที่ไม่สำเร็จ (ดูรายละเอียดด้านบน)", len(errors))
        return 1
    return 0


def print_summary(records: Sequence[Record]) -> None:
    labels = {"coop": "สหกรณ์ (แห่ง)", "member": "สมาชิก (คน)",
              "committee": "กรรมการ (คน)", "officer": "เจ้าหน้าที่ (คน)"}
    print()
    current = None
    for r in records:
        key = (r.data_year, r.sector, r.category)
        if key != current:
            current = key
            when = f"ปี {r.data_year} / {r.sector}" if r.data_year else "ปัจจุบัน"
            print(f"[{when}] {labels.get(r.category, r.category)}")
        print(f"    {r.metric:<11}{r.value:>15,}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    # ให้ console บน Windows แสดงภาษาไทยได้
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass
    return run(args)
