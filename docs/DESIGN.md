# CPD Big Data Scraper: วิเคราะห์โครงสร้างและออกแบบ

> เป้าหมาย: ดึงตัวเลขจากหน้าแรกของ https://bigdata.cpd.go.th/ (จำนวนสหกรณ์, สมาชิก, กรรมการ, เจ้าหน้าที่) ด้วย Python แล้วบันทึกเป็น CSV
> Repo: https://github.com/juiize/test-scraping
> สถานะ: v2 ดึงทั้งหน้าแรก (แท็บข้อมูลทั่วไป) ดูข้อ 9

---

## 1. วิเคราะห์ request ที่ได้มา

| รายการ | ค่า |
|---|---|
| Request | `GET https://bigdata.cpd.go.th/main.b908e72ce99cc4819d1d.js` |
| ประเภท | JS bundle ของ Angular (build แบบ dev ยังมี path ของ source `./src/app/...` อยู่) |
| ขนาด | ~9.2 MB |

**สรุป:** ไฟล์นี้ไม่มีตัวเลขที่แสดงในรูป แต่มีโค้ดที่บอกว่าหน้าเว็บไปเรียก API ตัวไหน ส่งพารามิเตอร์อะไร และคำนวณผลลัพธ์อย่างไร
จึงไม่ต้อง scrape HTML หรือใช้ browser ให้เรียก JSON API ตรงด้วย `requests` ได้เลย

### แหล่งข้อมูลในโค้ด

| ไฟล์ใน bundle | สิ่งที่ได้ |
|---|---|
| `src/environments/environment.ts` | `apiUrl2 = 'https://bigdata_api.cpd.go.th/apitest/'` (base URL ที่ service ใช้) |
| `src/app/services/Coop/coop-service.service.ts` | URL, method และ body ของแต่ละ endpoint |
| `src/app/components/callable.ts` | วิธีต่อ query string `?year=...&sector=...` |
| `src/app/pages/home/home.component.ts` | `ngOnInit()` ที่เรียก API และวิธีรวมตัวเลข |

- **Auth:** ไม่ต้องใช้ ส่วน `Authorization: Bearer ...` ถูก comment ทิ้งไว้ทั้งหมด
- **ค่า default ของ filter:** `OrgOrgId = PhakId = KhetId = "null"` (เป็น string) หมายถึงทั้งประเทศ

---

## 2. Endpoint ที่อยู่เบื้องหลังแต่ละการ์ด

Base: `https://bigdata_api.cpd.go.th/apitest/` ทุกตัวเป็น `POST`, `Content-Type: application/json`
Body: `{"OrgOrgId": "null", "PhakId": "null", "KhetId": "null"}`

| การ์ดในรูป | Endpoint | Query string | ฟิลด์ใน response | วิธีคำนวณบนหน้าเว็บ |
|---|---|---|---|---|
| จำนวนสหกรณ์ (รวม / Active / Non-active) | `api/CoopProfile/GetCoopOracleCountNEW` | ไม่มี | `coopCount`, `active`, `nonActive` | ใช้แถวสุดท้ายของ array (loop เขียนทับ ไม่ได้ sum) |
| จำนวนสมาชิกสหกรณ์ (ชาย / หญิง / รวม) | `api/Member/GetCoopSumMemberNew` | `year`, `sector` | `sum`, `dataM`, `dataFm` | sum ทุกแถว |
| จำนวนกรรมการ (ชาย / หญิง / รวม) | `api/CoopCommittee/GetCoopSumCommitteeNew` | `year`, `sector` | `sum`, `dataM`, `dataFm` | sum ทุกแถว |
| **จำนวนเจ้าหน้าที่สหกรณ์ (ชาย / หญิง / พนักงานรวม)** | `api/ProfileData/GetCoopSumOfficer` | `year`, `sector` (คนละแบบ ดูข้อ 3) | `sum`, `dataM`, `dataFm` | sum ทุกแถว |

ตัวอย่าง URL:
```
POST https://bigdata_api.cpd.go.th/apitest/api/ProfileData/GetCoopSumOfficer?year=2568&sector=null
POST https://bigdata_api.cpd.go.th/apitest/api/Member/GetCoopSumMemberNew?year=2568&sector=0
```

---

## 3. พารามิเตอร์และจุดที่ต้องระวัง

### `year`
- เป็นปี พ.ศ.
- ค่า default ของหน้าเว็บคือ `ปี ค.ศ. ปัจจุบัน - 1 + 543` (ปี 2026 ได้ **2568** ตรงกับ dropdown "ข้อมูล ณ ปี")
- ค่าที่เลือกได้คือ 2558 ถึงปีปัจจุบันลบ 1

### `sector` (dropdown "ภาคการเกษตร") มี 2 แบบ

| ตัวเลือก | สมาชิก / กรรมการ | เจ้าหน้าที่ (`isNonSector = true`) |
|---|---|---|
| ทั้งหมด | `0` | `null` (string) |
| ภาคการเกษตร | `1` | `สหกรณ์ภาคการเกษตร` (ต้อง URL-encode) |
| นอกภาคการเกษตร | `2` | `สหกรณ์นอกภาคการเกษตร` |

### ข้อสังเกตอื่น
- การ์ดจำนวนสหกรณ์ไม่ได้ส่ง `year`/`sector` ไป ตัวเลขจึงไม่เปลี่ยนตาม dropdown
- "ข้อมูล ณ วันที่ 28 ตุลาคม 2569" ไม่ได้มาจาก API หน้าเว็บคำนวณเป็นวันที่ของเมื่อวานเอง CSV จึงเก็บเวลาที่ดึงข้อมูล (`scraped_at`) แทน
- endpoint อยู่ใต้ path `/apitest/` ถ้าเว็บเปลี่ยน base URL ภายหลัง แก้ที่ `config.py` จุดเดียว

---

## 4. ออกแบบโปรแกรม

### โครงสร้าง repo

```
test-scraping/
├── cpd_scraper/
│   ├── __init__.py
│   ├── config.py      # BASE_URL, endpoint map, sector mapping 2 แบบ, timeout, headers
│   ├── client.py      # requests.Session + retry/backoff (urllib3 Retry) + timeout
│   ├── extract.py     # fetch_coop_count / fetch_members / fetch_committee / fetch_officers
│   ├── transform.py   # aggregate ตาม logic หน้าเว็บ + validate
│   └── writer.py      # เขียน CSV (utf-8-sig ให้ Excel เปิดภาษาไทยได้)
├── main.py            # CLI entry point
├── tests/
│   ├── fixtures/      # ตัวอย่าง JSON response
│   └── test_transform.py
├── data/              # output (อยู่ใน .gitignore)
├── requirements.txt   # requests (+ pytest สำหรับ dev)
├── .gitignore
└── README.md
```

### ขั้นตอนการทำงาน

```
CLI args (--year, --sector, --out, --all-years)
   │
   ▼
สร้าง list ของงาน (year × sector)
   │
   ▼
แต่ละงาน: เรียก 4 endpoint
   - ต่อ query ตาม sector mapping ของแต่ละ endpoint
   - POST พร้อม body = {"OrgOrgId":"null","PhakId":"null","KhetId":"null"}
   - retry 3 ครั้ง (backoff) และ timeout 30 วินาที
   │
   ▼
Transform
   - coop: ใช้แถวสุดท้าย → total / active / non_active
   - member, committee, officer: sum(sum), sum(dataM), sum(dataFm)
   - ถ้าค่าเป็น null ให้นับเป็น 0 และ log warning
   │
   ▼
Validate
   - male + female == total
   - active + non_active == total
   - ไม่ผ่าน: log warning แต่ยังเขียนไฟล์
   │
   ▼
เขียน CSV (append และเขียน header ถ้ายังไม่มีไฟล์)
```

### CLI ที่ตั้งใจไว้

```
python main.py                          # ปี default (2568), sector ทั้งหมด
python main.py --year 2567 --sector 1
python main.py --all-years --sector all # 2558 ถึงปีล่าสุด × 3 sector
python main.py --out data/cpd_summary.csv --wide
```

### HTTP headers
- `Content-Type: application/json`
- `Origin: https://bigdata.cpd.go.th`, `Referer: https://bigdata.cpd.go.th/` (ทำให้เหมือนเรียกจากหน้าเว็บ)
- `User-Agent` ที่ระบุตัวตนชัดเจน
- หน่วง 0.5 ถึง 1 วินาทีระหว่าง request เพื่อไม่ให้ server รับโหลดหนัก

---

## 5. รูปแบบ CSV

### แบบหลัก: long format (`data/cpd_summary.csv`)

| คอลัมน์ | ความหมาย |
|---|---|
| `scraped_at` | เวลาที่ดึง (ISO 8601, Asia/Bangkok) |
| `data_year` | ปี พ.ศ. ของข้อมูล (การ์ดสหกรณ์จะเว้นว่าง) |
| `sector` | ทั้งหมด / ภาคการเกษตร / นอกภาคการเกษตร |
| `category` | `coop` / `member` / `committee` / `officer` |
| `metric` | `total` / `active` / `non_active` / `male` / `female` |
| `value` | ตัวเลข (int) |
| `endpoint` | ชื่อ endpoint ที่ใช้ เพื่อ trace กลับได้ |

ตัวอย่าง (ค่าจากรูป):

```csv
scraped_at,data_year,sector,category,metric,value,endpoint
2026-10-29T21:00:00+07:00,,ทั้งหมด,coop,total,7563,GetCoopOracleCountNEW
2026-10-29T21:00:00+07:00,,ทั้งหมด,coop,active,6316,GetCoopOracleCountNEW
2026-10-29T21:00:00+07:00,,ทั้งหมด,coop,non_active,1247,GetCoopOracleCountNEW
2026-10-29T21:00:00+07:00,2568,ทั้งหมด,member,male,5828231,GetCoopSumMemberNew
2026-10-29T21:00:00+07:00,2568,ทั้งหมด,member,female,5084460,GetCoopSumMemberNew
2026-10-29T21:00:00+07:00,2568,ทั้งหมด,member,total,10912691,GetCoopSumMemberNew
2026-10-29T21:00:00+07:00,2568,ทั้งหมด,committee,male,36599,GetCoopSumCommitteeNew
2026-10-29T21:00:00+07:00,2568,ทั้งหมด,committee,female,27188,GetCoopSumCommitteeNew
2026-10-29T21:00:00+07:00,2568,ทั้งหมด,committee,total,63787,GetCoopSumCommitteeNew
2026-10-29T21:00:00+07:00,2568,ทั้งหมด,officer,male,11154,GetCoopSumOfficer
2026-10-29T21:00:00+07:00,2568,ทั้งหมด,officer,female,21040,GetCoopSumOfficer
2026-10-29T21:00:00+07:00,2568,ทั้งหมด,officer,total,32194,GetCoopSumOfficer
```

แบบ long นี้เพิ่มปีหรือ sector ได้โดยไม่ต้องเปลี่ยน schema และนำไป pivot ต่อได้ง่าย

### แบบเสริม: wide (`--wide`)
1 แถวต่อ (ปี, sector) คอลัมน์ได้แก่ `coop_total, coop_active, coop_non_active, member_male, member_female, member_total, committee_male, ..., officer_total`

---

## 6. ตรวจความถูกต้อง (ตัวเลขในรูปผ่านทุกข้อ)

| กลุ่ม | ชาย | หญิง | รวม | ผลรวมตรงกันไหม |
|---|---|---|---|---|
| สหกรณ์ | Active 6,316 | Non-active 1,247 | 7,563 | ✓ |
| สมาชิก | 5,828,231 | 5,084,460 | 10,912,691 | ✓ |
| กรรมการ | 36,599 | 27,188 | 63,787 | ✓ |
| เจ้าหน้าที่ | 11,154 | 21,040 | 32,194 | ✓ |

Unit test จะใช้ fixture JSON และ assert ว่าผลลัพธ์ตรงกับตัวเลขชุดนี้

---

## 7. ความเสี่ยงและสิ่งที่ต้องยืนยันก่อนเขียนโค้ด

1. **ยังไม่ได้เห็น JSON จริง:** ยิง API จาก sandbox ไม่ได้ (proxy 403) ชื่อฟิลด์ข้างบนจึงอนุมานจากโค้ดหน้าเว็บ ควรเปิด DevTools > Network ที่หน้าเว็บ หรือรันทดสอบ 1 ครั้งจากเครื่องในองค์กร แล้วเก็บ response เป็น fixture
2. **Network ขององค์กร:** request ผ่าน Skyhigh Secure Web Gateway อาจต้องตั้งค่า proxy/CA ให้ Python (`HTTPS_PROXY`, `REQUESTS_CA_BUNDLE`)
3. **สิทธิ์ repo:** ต้องเปิดสิทธิ์ push ของ `juiize/test-scraping` ให้ session ก่อนเริ่มเขียนโค้ด
4. **API เปลี่ยนได้:** path `/apitest/` และชื่อ `...New` บ่งบอกว่ายังพัฒนาอยู่ จึงแยก config ไว้ที่เดียว

## 8. ต่อยอด (เฟส 2)
- ข้อมูลรายจังหวัดจากแผนที่: `api/ProfileData/GetOracleSumProvinceYearSearch`, `api/Member/GetCoopMemberProvinceYearSearch`, `api/BusinessData/GetBussinessProvinceYearSum`
- ตั้ง schedule ให้รันรายวันหรือรายเดือน เก็บเป็น time series

---

## 9. v2: ดึงทั้งหน้าแรก (แท็บ "ข้อมูลทั่วไป")

จากการไล่ `home.component.ts` ทั้งไฟล์ (template + method ที่เรียก service) หน้าแรกใช้ endpoint ทั้งหมด 21 ตัว:

| key | endpoint | query | หมายเหตุ |
|---|---|---|---|
| coop_count | CoopProfile/GetCoopOracleCountNEW | - | การ์ดจำนวนสหกรณ์ |
| member_sum | Member/GetCoopSumMemberNew | year, sector | การ์ดสมาชิก |
| committee_sum | CoopCommittee/GetCoopSumCommitteeNew | year, sector | การ์ดกรรมการ |
| officer_sum | ProfileData/GetCoopSumOfficer | year, sector (non_sector) | การ์ดเจ้าหน้าที่ |
| map_coop_province | ProfileData/GetOracleSumProvinceYearSearch | - | แผนที่ (provinceName, sum, active, nonActive) |
| map_member_province | Member/GetCoopMemberProvinceYearSearch | year, sector | แผนที่ (provinceName, sum) |
| map_business_province | BusinessData/GetBussinessProvinceYearSum | year, sector | แผนที่ (provinceName, sum) ล้านบาท |
| standard_type | StandardData/GetCoopStandardTypeSum | year, sector | coopType, pass, notPass |
| coop_type_status | CoopProfile/GetCoopOracleTypesNEW | year, sector | |
| coop_type_level | CoopProfile/GetCoopTypeLevelCount | year, sector | level, count |
| coop_level | CoopProfile/GetCoopLevelCountNEW | year, sector | |
| finance | CoopProfile/GetCoopFinanceNew | year_change, sector | สินทรัพย์/หนี้สิน/ทุน/กำไร |
| finance_type | CoopProfile/GetCoopFinanceTypeNew | year_change, sector | |
| business | CoopProfile/GetCoopBussinessNew | year_change, sector | |
| business_type | CoopProfile/GetCoopBussinessTypeNew | year_change, sector | |
| participation | CoopProfile/GetCoopProfileBussinessNew | year_change, sector | การมีส่วนร่วม |
| participation_type | CoopProfile/GetCoopProfileBussinessTypeNew | year_change, sector | |
| oae_group | View/GetViewOAEByGroup | year_change, sector | groupCode, total_count, total_rai |
| oae_detail | View/GetViewOAEDetailByGroup | year_change, sector | body + groupCode "1"/"2"/"3" |
| rubber | View/GetViewRubberSumProvinceTotal | year_change, sector | total_count, total_rai |
| defect_province | Defect/GetDefectProvinceYearSum | sector | ปิดโดยค่าเริ่มต้น (หน้าเว็บแสดงเฉพาะผู้ล็อกอิน) |

ข้อสังเกต:
- `callable.setPathParam(URL, true)` ใช้ key **`year_change`** แทน `year`
- `GetDefectProvinceYearSum` ในหน้าเว็บต่อ `&sector=` โดยไม่มี `?` นำหน้า (URL ผิดรูป) scraper ส่งเป็น `?sector=` ที่ถูกต้องแทน
- แท็บ "ค้นหาข้อมูลราย เขต / ภาค", "อุปกรณ์การตลาด", "เครื่องจักรกลการเกษตร" เป็นคนละ route ไม่อยู่ในขอบเขตนี้

การเก็บข้อมูล:
- เก็บ **ทุกแถว ทุกฟิลด์** ของแต่ละ endpoint ลง `data/sections/<key>.csv` (flatten JSON ซ้อนเป็น `a.b`)
- รวมทุกค่าเป็นไฟล์เดียวแบบ long ที่ `data/cpd_page_long.csv`
- การ์ดสรุป 4 ใบยังคำนวณแบบเดิมที่ `data/cpd_summary.csv` / `cpd_summary_wide.csv`
- `data/run_log.csv` บันทึกผลทุก request; ถ้า endpoint ใดล้ม ส่วนอื่นยังเขียนไฟล์ได้ (exit code 1)
- section ที่ไม่ขึ้นกับปี/ภาคเรียกครั้งเดียว และ request ที่ซ้ำกันจะใช้ cache
