"""Entry point

ตัวอย่าง:
    python main.py                           # ปีล่าสุด, ทั้งหมด
    python main.py --year 2567 --sector 1
    python main.py --all-years --sector all --wide
    python main.py --save-raw -v             # เก็บ JSON ดิบไว้ตรวจสอบ
"""
import sys

from cpd_scraper.cli import main

if __name__ == "__main__":
    sys.exit(main())
