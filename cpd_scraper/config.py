"""ค่าคงที่และการตั้งค่าของ scraper (แก้ base URL / endpoint ได้ที่ไฟล์นี้ที่เดียว)

ที่มา: วิเคราะห์จาก JS bundle ของ https://bigdata.cpd.go.th/ (main.*.js)
  - src/environments/environment.ts               -> apiUrl2
  - src/app/services/Coop/coop-service.service.ts -> endpoint / body / query
  - src/app/components/callable.ts                -> query string year / year_change / sector
  - src/app/pages/home/home.component.ts          -> ข้อมูลที่หน้าแรก (แท็บ "ข้อมูลทั่วไป") ใช้
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

BASE_URL = "https://bigdata_api.cpd.go.th/apitest/"
SITE_URL = "https://bigdata.cpd.go.th"

# ใช้ timezone แบบคงที่ (+07:00) เพื่อไม่ต้องพึ่ง tzdata บน Windows
TZ_BANGKOK = timezone(timedelta(hours=7))

# body ที่หน้าแรกส่งไปทุก endpoint: "null" (string) = ทั้งประเทศ
DEFAULT_BODY: Dict[str, str] = {"OrgOrgId": "null", "PhakId": "null", "KhetId": "null"}

DEFAULT_HEADERS: Dict[str, str] = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": SITE_URL,
    "Referer": SITE_URL + "/",
    "User-Agent": "cpd-scraper/2.0 (+https://github.com/juiize/test-scraping)",
}

# ---- ภาค (dropdown "ภาคการเกษตร") ----
SECTOR_LABELS: Dict[str, str] = {
    "0": "ทั้งหมด",
    "1": "ภาคการเกษตร",
    "2": "นอกภาคการเกษตร",
}

# ค่า query `sector` แบบปกติ (callable.setPathParamSector(URL))
SECTOR_PARAM_STANDARD: Dict[str, str] = {"0": "0", "1": "1", "2": "2"}

# ค่า query `sector` แบบ isNonSector=true (callable.setPathParamSector(URL, true))
SECTOR_PARAM_NON_SECTOR: Dict[str, str] = {
    "0": "null",
    "1": "สหกรณ์ภาคการเกษตร",
    "2": "สหกรณ์นอกภาคการเกษตร",
}

# ---- ปี ----
FIRST_YEAR = 2558  # ปีแรกที่ dropdown ของหน้าเว็บให้เลือก
YEAR_DIFF = 1  # หน้าเว็บใช้ "ปีปัจจุบัน - 1" เป็นค่าเริ่มต้น


def current_be_year(now: Optional[datetime] = None) -> int:
    now = now or datetime.now(TZ_BANGKOK)
    return now.year + 543


def default_data_year(now: Optional[datetime] = None) -> int:
    """ปีข้อมูลเริ่มต้นแบบเดียวกับหน้าเว็บ: (ค.ศ. ปัจจุบัน - 1) + 543"""
    return current_be_year(now) - YEAR_DIFF


# =====================================================================
# Section = ข้อมูล 1 ชุดบนหน้าเว็บ = 1 endpoint (= 1 ไฟล์ CSV)
# =====================================================================
@dataclass(frozen=True)
class SectionSpec:
    key: str  # ชื่อไฟล์ CSV (data/sections/<key>.csv)
    title: str  # ชื่อส่วนบนหน้าเว็บ
    endpoint: str  # ชื่อ endpoint
    path: str  # path ต่อจาก BASE_URL
    year_key: Optional[str]  # "year" / "year_change" / None (= ไม่ส่งปี)
    sector_style: Optional[str]  # "standard" / "non_sector" / None (= ไม่ส่งภาค)
    body_variants: Tuple[Dict[str, str], ...] = ({},)  # body เพิ่มเติม (เรียก 1 ครั้งต่อ variant)
    default: bool = True  # ดึงโดยค่าเริ่มต้นหรือไม่
    note: str = ""

    @property
    def uses_year(self) -> bool:
        return self.year_key is not None

    @property
    def uses_sector(self) -> bool:
        return self.sector_style is not None


SECTIONS: Tuple[SectionSpec, ...] = (
    # ---------- การ์ดสรุปด้านบน ----------
    SectionSpec("coop_count", "จำนวนสหกรณ์ (Active / Non-active)",
                "GetCoopOracleCountNEW", "api/CoopProfile/GetCoopOracleCountNEW", None, None),
    SectionSpec("member_sum", "จำนวนสมาชิกสหกรณ์ (ชาย / หญิง)",
                "GetCoopSumMemberNew", "api/Member/GetCoopSumMemberNew", "year", "standard"),
    SectionSpec("committee_sum", "จำนวนกรรมการ (ชาย / หญิง)",
                "GetCoopSumCommitteeNew", "api/CoopCommittee/GetCoopSumCommitteeNew", "year", "standard"),
    SectionSpec("officer_sum", "จำนวนเจ้าหน้าที่สหกรณ์ (ชาย / หญิง)",
                "GetCoopSumOfficer", "api/ProfileData/GetCoopSumOfficer", "year", "non_sector"),

    # ---------- แผนที่ (รายจังหวัด) ----------
    SectionSpec("map_coop_province", "แผนที่: จำนวนสหกรณ์รายจังหวัด",
                "GetOracleSumProvinceYearSearch", "api/ProfileData/GetOracleSumProvinceYearSearch", None, None),
    SectionSpec("map_member_province", "แผนที่: จำนวนสมาชิกสหกรณ์รายจังหวัด",
                "GetCoopMemberProvinceYearSearch", "api/Member/GetCoopMemberProvinceYearSearch", "year", "standard"),
    SectionSpec("map_business_province", "แผนที่: ปริมาณธุรกิจสหกรณ์รายจังหวัด (ล้านบาท)",
                "GetBussinessProvinceYearSum", "api/BusinessData/GetBussinessProvinceYearSum", "year", "standard"),

    # ---------- มาตรฐาน / ประเภท / ระดับชั้น ----------
    SectionSpec("standard_type", "มาตรฐานสหกรณ์ (ผ่าน / ไม่ผ่าน รายประเภท)",
                "GetCoopStandardTypeSum", "api/StandardData/GetCoopStandardTypeSum", "year", "standard"),
    SectionSpec("coop_type_status", "จำนวนสหกรณ์รายประเภท (Active / Non-active)",
                "GetCoopOracleTypesNEW", "api/CoopProfile/GetCoopOracleTypesNEW", "year", "standard"),
    SectionSpec("coop_type_level", "ระดับชั้นความเข้มแข็ง รายประเภทสหกรณ์",
                "GetCoopTypeLevelCount", "api/CoopProfile/GetCoopTypeLevelCount", "year", "standard"),
    SectionSpec("coop_level", "ระดับชั้นความเข้มแข็ง (รวม)",
                "GetCoopLevelCountNEW", "api/CoopProfile/GetCoopLevelCountNEW", "year", "standard"),

    # ---------- การเงิน (สินทรัพย์ / หนี้สิน / ทุน / กำไร) ----------
    SectionSpec("finance", "สินทรัพย์ / หนี้สิน / ทุน / กำไร(ขาดทุน) ของสหกรณ์",
                "GetCoopFinanceNew", "api/CoopProfile/GetCoopFinanceNew", "year_change", "standard"),
    SectionSpec("finance_type", "การเงินของสหกรณ์ รายประเภท",
                "GetCoopFinanceTypeNew", "api/CoopProfile/GetCoopFinanceTypeNew", "year_change", "standard"),

    # ---------- ปริมาณธุรกิจ ----------
    SectionSpec("business", "ปริมาณธุรกิจ รวมทุกประเภทสหกรณ์",
                "GetCoopBussinessNew", "api/CoopProfile/GetCoopBussinessNew", "year_change", "standard"),
    SectionSpec("business_type", "ปริมาณธุรกิจ รายประเภทสหกรณ์",
                "GetCoopBussinessTypeNew", "api/CoopProfile/GetCoopBussinessTypeNew", "year_change", "standard"),

    # ---------- การมีส่วนร่วมของสมาชิก ----------
    SectionSpec("participation", "การมีส่วนร่วมของสมาชิกสหกรณ์ ทุกประเภท",
                "GetCoopProfileBussinessNew", "api/CoopProfile/GetCoopProfileBussinessNew", "year_change", "standard"),
    SectionSpec("participation_type", "การมีส่วนร่วมของสมาชิกสหกรณ์ รายประเภท",
                "GetCoopProfileBussinessTypeNew", "api/CoopProfile/GetCoopProfileBussinessTypeNew",
                "year_change", "standard"),

    # ---------- ทะเบียนเกษตรกร (OAE) / ผู้ปลูกยาง ----------
    SectionSpec("oae_group", "ทะเบียนเกษตรกร / เลี้ยงสัตว์ / ประมง (รวม)",
                "GetViewOAEByGroup", "api/View/GetViewOAEByGroup", "year_change", "standard"),
    SectionSpec("oae_detail", "ทะเบียนเกษตรกร / เลี้ยงสัตว์ / ประมง (รายประเภท)",
                "GetViewOAEDetailByGroup", "api/View/GetViewOAEDetailByGroup", "year_change", "standard",
                body_variants=({"groupCode": "1"}, {"groupCode": "2"}, {"groupCode": "3"}),
                note="groupCode 1=ทะเบียนเกษตรกร 2=ทะเบียนเลี้ยงสัตว์ 3=ทะเบียนประมง"),
    SectionSpec("rubber", "ทะเบียนผู้ปลูกยาง",
                "GetViewRubberSumProvinceTotal", "api/View/GetViewRubberSumProvinceTotal", "year_change", "standard"),

    # ---------- ต้องล็อกอินบนหน้าเว็บ (ปิดไว้โดยค่าเริ่มต้น) ----------
    SectionSpec("defect_province", "ข้อบกพร่องรายจังหวัด (แสดงเฉพาะผู้ที่ล็อกอิน)",
                "GetDefectProvinceYearSum", "api/Defect/GetDefectProvinceYearSum", None, "standard",
                default=False, note="หน้าเว็บแสดงเฉพาะผู้ใช้ที่ล็อกอินและมีสิทธิ์"),
)

SECTIONS_BY_KEY: Dict[str, SectionSpec] = {s.key: s for s in SECTIONS}

OAE_GROUP_LABELS = {"1": "ทะเบียนเกษตรกร", "2": "ทะเบียนเลี้ยงสัตว์", "3": "ทะเบียนประมง"}


# =====================================================================
# Summary = ตัวเลขบนการ์ดสรุป (คำนวณแบบเดียวกับหน้าเว็บ)
# =====================================================================
@dataclass(frozen=True)
class SummarySpec:
    category: str  # coop / member / committee / officer
    section: str  # key ของ SectionSpec ที่ใช้
    aggregate: str  # "last" (ใช้แถวสุดท้าย) หรือ "sum" (รวมทุกแถว)
    fields: Dict[str, str] = field(default_factory=dict)  # metric -> ชื่อฟิลด์ใน JSON

    @property
    def spec(self) -> SectionSpec:
        return SECTIONS_BY_KEY[self.section]

    # ให้ใช้แทน SectionSpec ได้ในจุดที่ต้องการ name/path/uses_year
    @property
    def name(self) -> str:
        return self.spec.endpoint

    @property
    def path(self) -> str:
        return self.spec.path

    @property
    def uses_year(self) -> bool:
        return self.spec.uses_year


SUMMARIES: Tuple[SummarySpec, ...] = (
    SummarySpec("coop", "coop_count", "last",
                {"total": "coopCount", "active": "active", "non_active": "nonActive"}),
    SummarySpec("member", "member_sum", "sum", {"male": "dataM", "female": "dataFm", "total": "sum"}),
    SummarySpec("committee", "committee_sum", "sum", {"male": "dataM", "female": "dataFm", "total": "sum"}),
    SummarySpec("officer", "officer_sum", "sum", {"male": "dataM", "female": "dataFm", "total": "sum"}),
)

SUMMARIES_BY_CATEGORY: Dict[str, SummarySpec] = {s.category: s for s in SUMMARIES}

# ลำดับคอลัมน์ของไฟล์ summary แบบ wide
WIDE_COLUMNS = [
    "coop_total", "coop_active", "coop_non_active",
    "member_male", "member_female", "member_total",
    "committee_male", "committee_female", "committee_total",
    "officer_male", "officer_female", "officer_total",
]
