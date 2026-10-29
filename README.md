# test-scraping: CPD Big Data scraper

ดึงข้อมูล **ทั้งหน้าแรก** (แท็บ "ข้อมูลทั่วไป") ของ [bigdata.cpd.go.th](https://bigdata.cpd.go.th/#/) (กรมส่งเสริมสหกรณ์) แล้วบันทึกเป็น CSV

- เก็บ **ทุกแถวและทุกฟิลด์** ที่ API ส่งกลับ ไม่ได้เก็บแค่ยอดรวม เช่น ข้อมูลรายจังหวัดของแผนที่, รายประเภทสหกรณ์, รายระดับชั้น
- คำนวณ **การ์ดสรุป** (สหกรณ์ / สมาชิก / กรรมการ / เจ้าหน้าที่) แบบเดียวกับหน้าเว็บไว้อีกไฟล์

ไม่ได้ scrape HTML แต่เรียก JSON API ตัวเดียวกับที่หน้าเว็บใช้ รายละเอียดการวิเคราะห์อยู่ใน [docs/DESIGN.md](docs/DESIGN.md)

---

## ติดตั้ง (PowerShell)

ต้องใช้ Python 3.9 ขึ้นไป (แนะนำ 3.10+)

```powershell
cd $HOME\Desktop\CPD\test-scraping
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## วิธีใช้

```powershell
python main.py                                # ทั้งหน้า ปีล่าสุด (เหมือนหน้าเว็บ) ภาคทั้งหมด
python main.py --year 2567 --sector 1         # เลือกปี (พ.ศ.) และภาค
python main.py --all-years --sector all       # ย้อนหลัง 2558 ถึงปีล่าสุด x 3 ภาค
python main.py --sections map_coop_province,finance   # เลือกเฉพาะบาง section
python main.py --summary-only                 # เฉพาะการ์ดสรุป 4 ใบ
python main.py --list-sections                # ดูรายชื่อ section ทั้งหมด
python main.py --save-raw -v                  # เก็บ JSON ดิบไว้ที่ data\raw\
```

| ตัวเลือก | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `--year` | ปีปัจจุบัน − 1 (พ.ศ.) | ปีข้อมูล |
| `--all-years` | | ดึงตั้งแต่ 2558 ถึงปีล่าสุด |
| `--sector` | `0` | `0`=ทั้งหมด, `1`=ภาคการเกษตร, `2`=นอกภาคการเกษตร, `all` |
| `--sections` | ทุก section ที่เปิดไว้ | คั่นด้วยจุลภาค หรือ `all` (รวม `defect_province`) |
| `--summary-only` | | เฉพาะ 4 section ของการ์ดสรุป |
| `--out-dir` | `data` | โฟลเดอร์ output |
| `--overwrite` | | เขียนทับแทน append ต่อท้าย |
| `--save-raw [DIR]` | `data\raw` | เก็บ JSON ดิบของแต่ละ request |
| `--delay` / `--timeout` | `0.5` / `30` | วินาที |
| `--ca-bundle` | | ไฟล์ CA (.pem) ของ proxy องค์กร |

Exit code: `0` = สำเร็จ, `1` = สำเร็จบางส่วน (ดู `run_log.csv`), `2` = ไม่ได้ข้อมูลเลย

## ข้อมูลที่ดึง (section)

| key | ส่วนบนหน้าเว็บ | ปี | ภาค |
|---|---|---|---|
| `coop_count` | จำนวนสหกรณ์ (Active / Non-active) | - | - |
| `member_sum` | จำนวนสมาชิกสหกรณ์ (ชาย / หญิง) | ✓ | ✓ |
| `committee_sum` | จำนวนกรรมการ (ชาย / หญิง) | ✓ | ✓ |
| `officer_sum` | จำนวนเจ้าหน้าที่สหกรณ์ (ชาย / หญิง) | ✓ | ✓ |
| `map_coop_province` | แผนที่: จำนวนสหกรณ์รายจังหวัด | - | - |
| `map_member_province` | แผนที่: จำนวนสมาชิกสหกรณ์รายจังหวัด | ✓ | ✓ |
| `map_business_province` | แผนที่: ปริมาณธุรกิจสหกรณ์รายจังหวัด (ล้านบาท) | ✓ | ✓ |
| `standard_type` | มาตรฐานสหกรณ์ (ผ่าน / ไม่ผ่าน รายประเภท) | ✓ | ✓ |
| `coop_type_status` | จำนวนสหกรณ์รายประเภท (Active / Non-active) | ✓ | ✓ |
| `coop_type_level` | ระดับชั้นความเข้มแข็ง รายประเภท | ✓ | ✓ |
| `coop_level` | ระดับชั้นความเข้มแข็ง (รวม) | ✓ | ✓ |
| `finance` | สินทรัพย์ / หนี้สิน / ทุน / กำไร(ขาดทุน) | ✓ | ✓ |
| `finance_type` | การเงินรายประเภทสหกรณ์ | ✓ | ✓ |
| `business` | ปริมาณธุรกิจ รวมทุกประเภท | ✓ | ✓ |
| `business_type` | ปริมาณธุรกิจ รายประเภท | ✓ | ✓ |
| `participation` | การมีส่วนร่วมของสมาชิก ทุกประเภท | ✓ | ✓ |
| `participation_type` | การมีส่วนร่วมของสมาชิก รายประเภท | ✓ | ✓ |
| `oae_group` | ทะเบียนเกษตรกร / เลี้ยงสัตว์ / ประมง (รวม) | ✓ | ✓ |
| `oae_detail` | ทะเบียนฯ รายประเภท (`req_groupCode` 1=เกษตรกร 2=เลี้ยงสัตว์ 3=ประมง) | ✓ | ✓ |
| `rubber` | ทะเบียนผู้ปลูกยาง | ✓ | ✓ |
| `defect_province` | ข้อบกพร่องรายจังหวัด **(ปิดไว้ หน้าเว็บแสดงเฉพาะผู้ที่ล็อกอิน)** | - | ✓ |

section ที่ไม่ขึ้นกับปี/ภาค จะดึงแค่ครั้งเดียวต่อการรัน แม้สั่ง `--all-years --sector all`

แท็บอื่นบนหน้าเว็บ ("ค้นหาข้อมูลราย เขต / ภาค", "อุปกรณ์การตลาด", "เครื่องจักรกลการเกษตร") เป็นคนละหน้า ยังไม่ได้รวมไว้

## ไฟล์ output (`data\`)

| ไฟล์ | รูปแบบ |
|---|---|
| `sections\<key>.csv` | 1 ไฟล์ต่อ section: `scraped_at, data_year, sector, [req_groupCode], row_no` + **ทุกฟิลด์จาก API** (ฟิลด์ซ้อนเป็น `a.b`) |
| `cpd_page_long.csv` | ทุกค่าบนหน้าในไฟล์เดียว: `scraped_at, section, section_title, data_year, sector, request, row_no, field, value` |
| `cpd_summary.csv` | การ์ดสรุปแบบ long: `scraped_at, data_year, sector, category, metric, value, endpoint` |
| `cpd_summary_wide.csv` | การ์ดสรุปแบบ wide: 1 แถวต่อปีต่อภาค |
| `run_log.csv` | ผลของทุก request: section, ปี, ภาค, status, จำนวนแถว, URL, error |
| `raw\*.json` | JSON ดิบ (เมื่อใช้ `--save-raw`) |

ทุกไฟล์เป็น UTF-8 แบบมี BOM ดับเบิลคลิกเปิดใน Excel แล้วภาษาไทยแสดงถูกต้อง
ถ้า API เพิ่มฟิลด์ใหม่ ไฟล์ราย section จะเพิ่มคอลัมน์ให้อัตโนมัติ

ชื่อคอลัมน์ในไฟล์ราย section ใช้ชื่อฟิลด์จาก API ตรง ๆ (เช่น `provinceName`, `sum`, `active`, `nonActive`, `coopType`, `total_count`, `total_rai`)

## API ที่ใช้

Base: `https://bigdata_api.cpd.go.th/apitest/` ทุกตัวเป็น `POST` body `{"OrgOrgId":"null","PhakId":"null","KhetId":"null"}`
(`oae_detail` เพิ่ม `"groupCode"`) ดู path และ query ของแต่ละ section ได้ใน `cpd_scraper/config.py` หรือ `python main.py --list-sections`

query string มี 3 แบบตามที่หน้าเว็บส่ง:
- `?year=2568&sector=0|1|2`
- `?year_change=2568&sector=0|1|2` (finance / business / participation / oae / rubber)
- `?year=2568&sector=null|สหกรณ์ภาคการเกษตร|สหกรณ์นอกภาคการเกษตร` (officer)

## โครงสร้างโปรเจกต์

```
cpd_scraper/
  config.py     base URL, รายการ section, mapping ภาค/ฟิลด์
  client.py     requests.Session + retry + timeout
  extract.py    ดึงทุก section (ไม่เรียกซ้ำ) + คำนวณการ์ดสรุป
  transform.py  รวมตัวเลข, ตรวจ male+female == total, flatten JSON
  writer.py     เขียน CSV ทุกไฟล์
  cli.py        argument parser
main.py         entry point
tests/          unit test (ไม่ยิงเน็ตจริง)
docs/DESIGN.md  การวิเคราะห์และออกแบบ
```

## รัน test

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

## แก้ปัญหา

| อาการ | วิธีแก้ |
|---|---|
| `SSLError` / `CERTIFICATE_VERIFY_FAILED` | ใช้ Python 3.10+ แล้ว `pip install -r requirements.txt` อีกครั้ง (ติดตั้ง `truststore` ให้ใช้ใบรับรองของ Windows) หรือใช้ `--ca-bundle path\to\corp-ca.pem` |
| `ProxyError` / timeout | ตั้ง `$env:HTTPS_PROXY="http://<proxy>:<port>"` ก่อนรัน |
| บาง section `error` ใน `run_log.csv` | ดูคอลัมน์ `error` ถ้าเป็น 404 / 500 แปลว่า endpoint นั้นเปลี่ยนหรือปิด ส่วนอื่นยังเขียนไฟล์ตามปกติ |
| `ไม่พบฟิลด์ [...]` (การ์ดสรุป) | API เปลี่ยนชื่อฟิลด์ ดูชื่อจริงในข้อความ error แล้วแก้ `SUMMARIES` ใน `cpd_scraper/config.py` |
| ตัวเลขไม่ตรงหน้าเว็บ | รัน `--save-raw -v` แล้วเทียบ `data\raw\*.json` กับ DevTools > Network ของหน้าเว็บ |

> หมายเหตุ: endpoint และพารามิเตอร์วิเคราะห์จากโค้ดหน้าเว็บ (`main.*.js` ณ 13/07/2569) ตอนรันครั้งแรกแนะนำให้ใช้ `--save-raw` เพื่อยืนยัน แล้วนำ JSON จริงไปแทน `tests/fixtures/`
