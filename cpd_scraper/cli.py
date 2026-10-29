"""Command-line interface: python main.py --help"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

from . import config
from .client import CpdClient, use_os_trust_store
from .extract import PageFetcher, Record, build_summary
from .writer import write_long, write_page_long, write_run_log, write_sections, write_wide

log = logging.getLogger("cpd_scraper")

SUMMARY_SECTION_KEYS = [s.section for s in config.SUMMARIES]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    default_year = config.default_data_year()
    p = argparse.ArgumentParser(
        prog="python main.py",
        description="ดึงข้อมูลทั้งหน้าแรก (แท็บข้อมูลทั่วไป) ของ bigdata.cpd.go.th แล้วบันทึกเป็น CSV",
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument("--year", type=int, default=default_year,
                   help=f"ปีข้อมูล (พ.ศ.) ค่าเริ่มต้น {default_year} เหมือนหน้าเว็บ")
    g.add_argument("--all-years", action="store_true",
                   help=f"ดึงทุกปีตั้งแต่ {config.FIRST_YEAR} ถึง {default_year}")
    p.add_argument("--sector", choices=["0", "1", "2", "all"], default="0",
                   help="0=ทั้งหมด (ค่าเริ่มต้น), 1=ภาคการเกษตร, 2=นอกภาคการเกษตร, all=ทั้ง 3 แบบ")

    sel = p.add_mutually_exclusive_group()
    sel.add_argument("--sections", default=None, metavar="KEYS",
                     help="เลือกเฉพาะบาง section คั่นด้วยจุลภาค เช่น officer_sum,finance "
                          "หรือ all (รวม section ที่ปิดไว้) ดูรายชื่อด้วย --list-sections")
    sel.add_argument("--summary-only", action="store_true",
                     help="ดึงเฉพาะการ์ดสรุป 4 ใบ (สหกรณ์/สมาชิก/กรรมการ/เจ้าหน้าที่)")
    p.add_argument("--list-sections", action="store_true", help="แสดงรายชื่อ section ทั้งหมดแล้วจบ")

    p.add_argument("--out-dir", type=Path, default=Path("data"),
                   help="โฟลเดอร์ output (ค่าเริ่มต้น data)")
    p.add_argument("--overwrite", action="store_true",
                   help="เขียนทับไฟล์เดิม (ค่าเริ่มต้นคือ append ต่อท้าย)")
    p.add_argument("--save-raw", nargs="?", type=Path, const=True, default=None, metavar="DIR",
                   help="เก็บ JSON ดิบของแต่ละ request (ค่าเริ่มต้น <out-dir>/raw)")
    p.add_argument("--base-url", default=config.BASE_URL, help="base URL ของ API")
    p.add_argument("--timeout", type=float, default=30.0, help="timeout ต่อ request (วินาที)")
    p.add_argument("--delay", type=float, default=0.5, help="หน่วงระหว่าง request (วินาที)")
    p.add_argument("--ca-bundle", type=Path, default=None,
                   help="ไฟล์ CA (.pem) ของ proxy องค์กร กรณีเจอ SSL error")
    p.add_argument("-v", "--verbose", action="store_true", help="แสดง log ละเอียด")
    args = p.parse_args(argv)

    args.years = (list(range(default_year, config.FIRST_YEAR - 1, -1))
                  if args.all_years else [args.year])
    args.sector_codes = ["0", "1", "2"] if args.sector == "all" else [args.sector]

    if args.summary_only:
        keys = SUMMARY_SECTION_KEYS
    elif args.sections is None:
        keys = [s.key for s in config.SECTIONS if s.default]
    elif args.sections.strip().lower() == "all":
        keys = [s.key for s in config.SECTIONS]
    else:
        keys = [k.strip() for k in args.sections.split(",") if k.strip()]
        unknown = [k for k in keys if k not in config.SECTIONS_BY_KEY]
        if unknown:
            p.error(f"ไม่รู้จัก section: {', '.join(unknown)} (ดูรายชื่อด้วย --list-sections)")
    args.section_specs = [config.SECTIONS_BY_KEY[k] for k in keys]

    if args.save_raw is True:
        args.save_raw = args.out_dir / "raw"
    return args


def list_sections() -> None:
    print(f"{'key':<22} {'ค่าเริ่มต้น':<10} {'ปี':<12} {'ภาค':<11} ชื่อบนหน้าเว็บ")
    for s in config.SECTIONS:
        print(f"{s.key:<22} {'ดึง' if s.default else 'ปิด':<10} {s.year_key or '-':<12} "
              f"{s.sector_style or '-':<11} {s.title}")


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
    ts = scraped_at.isoformat(timespec="seconds")
    append = not args.overwrite
    out = args.out_dir

    fetcher = PageFetcher(client, scraped_at, raw_dir=args.save_raw)
    results = fetcher.fetch_page(args.section_specs, args.years, args.sector_codes)
    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]

    write_run_log(results, out / "run_log.csv", ts, append=append)
    if not ok:
        log.error("ไม่ได้ข้อมูลเลย (ดู %s)", out / "run_log.csv")
        return 2

    counts = write_sections(ok, out / "sections", ts, append=append)
    n_long = write_page_long(ok, out / "cpd_page_long.csv", ts, append=append)

    records, summary_errors = build_summary(ok, scraped_at)
    if records:
        write_long(records, out / "cpd_summary.csv", append=append)
        write_wide(records, out / "cpd_summary_wide.csv", append=append)

    print_report(args.section_specs, counts, n_long, records, out)

    if failed or summary_errors:
        log.warning("มี %d request ที่ไม่สำเร็จ / %d summary ที่คำนวณไม่ได้ (ดู %s)",
                    len(failed), len(summary_errors), out / "run_log.csv")
        return 1
    return 0


def print_report(sections, counts, n_long: int, records: List[Record], out: Path) -> None:
    print()
    print(f"ไฟล์ราย section -> {out / 'sections'}")
    for s in sections:
        n = counts.get(s.key)
        status = f"{n:>6,} แถว" if n is not None else "     ไม่มีข้อมูล"
        print(f"    {s.key:<22}{status}   {s.title}")
    print(f"รวมทุกค่าบนหน้า   -> {out / 'cpd_page_long.csv'} ({n_long:,} ค่า)")
    if records:
        print(f"การ์ดสรุป          -> {out / 'cpd_summary.csv'}, {out / 'cpd_summary_wide.csv'}")
        print_summary(records)


def print_summary(records: Sequence[Record]) -> None:
    labels = {"coop": "สหกรณ์ (แห่ง)", "member": "สมาชิก (คน)",
              "committee": "กรรมการ (คน)", "officer": "เจ้าหน้าที่ (คน)"}
    current = None
    for r in records:
        key = (r.data_year, r.sector, r.category)
        if key != current:
            current = key
            when = f"ปี {r.data_year} / {r.sector}" if r.data_year else "ปัจจุบัน"
            print(f"  [{when}] {labels.get(r.category, r.category)}")
        print(f"      {r.metric:<11}{r.value:>15,}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    # ให้ console บน Windows แสดงภาษาไทยได้
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass
    args = parse_args(argv)
    if args.list_sections:
        list_sections()
        return 0
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    return run(args)
