"""Entry point

ตัวอย่าง:
    python main.py                               # ทั้งหน้า ปีล่าสุด ภาคทั้งหมด
    python main.py --year 2567 --sector 1        # เลือกปี/ภาค
    python main.py --all-years --sector all      # ย้อนหลังทุกปี x 3 ภาค
    python main.py --sections officer_sum,finance
    python main.py --summary-only                # เฉพาะการ์ดสรุป 4 ใบ
    python main.py --list-sections               # ดูรายชื่อ section
    python main.py --save-raw -v                 # เก็บ JSON ดิบไว้ตรวจสอบ
"""
import sys

from cpd_scraper.cli import main

if __name__ == "__main__":
    sys.exit(main())
