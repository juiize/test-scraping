# test-scraping: CPD Big Data scraper

ดึงตัวเลขสรุปจากหน้าแรกของ [bigdata.cpd.go.th](https://bigdata.cpd.go.th/) (กรมส่งเสริมสหกรณ์) แล้วบันทึกเป็น CSV

| การ์ดบนหน้าเว็บ | ค่าที่เก็บ |
|---|---|
| จำนวนสหกรณ์ | รวม / Active / Non-active |
| จำนวนสมาชิกสหกรณ์ | ชาย / หญิง / รวม |
| จำนวนกรรมการ | ชาย / หญิง / รวม |
| **จำนวนเจ้าหน้าที่สหกรณ์** | ชาย / หญิง / รวม (พนักงาน) |

ไม่ได้ scrape HTML แต่เรียก JSON API ตัวเดียวกับที่หน้าเว็บใช้ รายละเอียดการวิเคราะห์อยู่ใน [docs/DESIGN.md](docs/DESIGN.md)

---

## ติดตั้ง

ต้องใช้ Python 3.9 ขึ้นไป (แนะนำ 3.10+)

```bash
cd test-scraping
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

## วิธีใช้

```bash
python main.py                                  # ปีล่าสุด (เหมือนหน้าเว็บ), ภาคทั้งหมด
python main.py --year 2567                      # เลือกปี (พ.ศ.)
python main.py --sector 1                       # 0=ทั้งหมด 1=ภาคการเกษตร 2=นอกภาคการเกษตร
python main.py --all-years --sector all --wide  # ย้อนหลังทุกปี x 3 ภาค + ไฟล์ wide
python main.py --save-raw -v                    # เก็บ JSON ดิบไว้ที่ data/raw/
python main.py --help                           # ดูตัวเลือกทั้งหมด
```

ตัวอย่างผลลัพธ์บนหน้าจอ:

```
[ปัจจุบัน] สหกรณ์ (แห่ง)
    total                7,563
    active               6,316
    non_active           1,247
[ปี 2568 / ทั้งหมด] เจ้าหน้าที่ (คน)
    male                11,154
    female              21,040
    total               32,194
...
```

| ตัวเลือก | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `--year` | ปีปัจจุบัน − 1 (พ.ศ.) | ปีข้อมูล |
| `--all-years` | | ดึงตั้งแต่ 2558 ถึงปีล่าสุด |
| `--sector` | `0` | `0`, `1`, `2` หรือ `all` |
| `--out` | `data/cpd_summary.csv` | ไฟล์ output (append ต่อท้ายถ้ามีไฟล์อยู่แล้ว) |
| `--overwrite` | | เขียนทับแทน append |
| `--wide` | | เขียน `<out>_wide.csv` เพิ่ม |
| `--save-raw [DIR]` | `data/raw` | เก็บ JSON ดิบของแต่ละ request |
| `--delay` | `0.5` | หน่วงระหว่าง request (วินาที) |
| `--timeout` | `30` | timeout ต่อ request (วินาที) |
| `--ca-bundle` | | ไฟล์ CA (.pem) ของ proxy องค์กร |

Exit code: `0` = สำเร็จ, `1` = สำเร็จบางส่วน, `2` = ไม่ได้ข้อมูลเลย

## รูปแบบ CSV

### `data/cpd_summary.csv` (long: 1 แถวต่อ 1 ตัวเลข)

| คอลัมน์ | ตัวอย่าง | หมายเหตุ |
|---|---|---|
| `scraped_at` | `2026-10-29T21:00:00+07:00` | เวลาที่ดึง |
| `data_year` | `2568` | ว่างสำหรับ `coop` เพราะ API ไม่รับปี |
| `sector` | `ทั้งหมด` | |
| `category` | `officer` | `coop` / `member` / `committee` / `officer` |
| `metric` | `total` | `total` / `active` / `non_active` / `male` / `female` |
| `value` | `32194` | |
| `endpoint` | `GetCoopSumOfficer` | |

### `data/cpd_summary_wide.csv` (`--wide`: 1 แถวต่อปีต่อภาค)

`scraped_at, data_year, sector, coop_total, coop_active, coop_non_active, member_male, member_female, member_total, committee_male, committee_female, committee_total, officer_male, officer_female, officer_total`

ไฟล์ทั้งสองเป็น UTF-8 แบบมี BOM ดับเบิลคลิกเปิดใน Excel แล้วภาษาไทยแสดงถูกต้อง

## API ที่ใช้

Base: `https://bigdata_api.cpd.go.th/apitest/` ทุกตัวเป็น `POST` และส่ง body `{"OrgOrgId":"null","PhakId":"null","KhetId":"null"}`

| category | endpoint | query |
|---|---|---|
| coop | `api/CoopProfile/GetCoopOracleCountNEW` | ไม่มี |
| member | `api/Member/GetCoopSumMemberNew` | `year`, `sector=0/1/2` |
| committee | `api/CoopCommittee/GetCoopSumCommitteeNew` | `year`, `sector=0/1/2` |
| officer | `api/ProfileData/GetCoopSumOfficer` | `year`, `sector=null/สหกรณ์ภาคการเกษตร/สหกรณ์นอกภาคการเกษตร` |

ถ้า API เปลี่ยน path หรือชื่อฟิลด์ ให้แก้ที่ `cpd_scraper/config.py` ไฟล์เดียว

## โครงสร้างโปรเจกต์

```
cpd_scraper/
  config.py     base URL, endpoint, mapping ภาค/ฟิลด์
  client.py     requests.Session + retry + timeout
  extract.py    เรียก API แล้วแปลงเป็น Record
  transform.py  รวมตัวเลข + ตรวจ male+female == total
  writer.py     เขียน CSV long / wide
  cli.py        argument parser
main.py         entry point
tests/          unit test (ไม่ยิงเน็ตจริง)
docs/DESIGN.md  การวิเคราะห์และออกแบบ
```

## รัน test

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## แก้ปัญหา

| อาการ | วิธีแก้ |
|---|---|
| `SSLError` / `CERTIFICATE_VERIFY_FAILED` | ใช้ Python 3.10+ แล้ว `pip install -r requirements.txt` อีกครั้ง (ติดตั้ง `truststore` ให้ใช้ใบรับรองของ Windows) หรือส่ง `--ca-bundle path\to\corp-ca.pem` |
| `ProxyError` / timeout | ตั้ง `set HTTPS_PROXY=http://<proxy>:<port>` ก่อนรัน |
| `ไม่พบฟิลด์ [...] ใน response` | API เปลี่ยนชื่อฟิลด์ ดูชื่อจริงในข้อความ error แล้วแก้ `fields` ใน `cpd_scraper/config.py` |
| ตัวเลขไม่ตรงหน้าเว็บ | รัน `--save-raw -v` แล้วเปิด `data/raw/*.json` เทียบกับ DevTools > Network ของหน้าเว็บ |

> หมายเหตุ: ชื่อฟิลด์ใน response อนุมานจากโค้ดหน้าเว็บ ตอนรันครั้งแรกแนะนำให้ใช้ `--save-raw` เพื่อยืนยัน แล้วนำ JSON จริงไปแทน `tests/fixtures/`
