# Test fixtures

ไฟล์ `<section key>.json` คือตัวอย่าง response ที่ **สร้างขึ้นเอง** ไม่ใช่ JSON จริงจาก API

- `coop_count`, `member_sum`, `committee_sum`, `officer_sum` ตั้งค่าให้ผลรวมตรงกับตัวเลขบนหน้าเว็บ (ข้อมูล ณ ปี 2568)
- section อื่นใช้ชื่อฟิลด์ตามที่โค้ดหน้าเว็บอ่าน (เช่น `provinceName`, `sum`, `coopType`, `total_count`) ค่าเป็นตัวเลขสมมติ
- `oae_detail.json` แยกตาม `groupCode` (1=ทะเบียนเกษตรกร, 2=เลี้ยงสัตว์, 3=ประมง)

เมื่อรัน `python main.py --save-raw` ได้แล้ว ให้นำไฟล์ใน `data/raw/` มาแทน (เก็บเฉพาะ array ใน key `rows`)
