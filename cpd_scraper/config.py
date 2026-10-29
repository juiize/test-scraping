"""ค่าคงที่และการตั้งค่าของ scraper (แก้ base URL / endpoint ได้ที่ไฟล์นี้ที่เดียว)

ที่มา: วิเคราะห์จาก JS bundle ของ https://bigdata.cpd.go.th/ (main.*.js)
  - src/environments/environment.ts           -> apiUrl2
  - src/app/services/Coop/coop-service.service.ts -> endpoint / body
  - src/app/components/callable.ts           -> query string year / sector
  - src/app/pages/home/home.component.ts     -> วิธีรวมตัวเลขบนการ์ด
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

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
    "User-Agent": "cpd-scraper/1.0 (+https://github.com/juiize/test-scraping)",
}

# ---- ภาค (dropdown "ภาคการเกษตร") ----
SECTOR_LABELS: Dict[str, str] = {
    "0": "ทั้งหมด",
    "1": "ภาคการเกษตร",
    "2": "นอกภาคการเกษตร",
}

# ค่า query `sector` แบบปกติ (สมาชิก / กรรมการ)
SECTOR_PARAM_STANDARD: Dict[str, str] = {"0": "0", "1": "1", "2": "2"}

# ค่า query `sector` แบบ isNonSector=true (ใช้กับ GetCoopSumOfficer)
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


# ---- Endpoint ----
@dataclass(frozen=True)
class EndpointSpec:
    category: str  # coop / member / committee / officer
    name: str  # ชื่อ endpoint (ใช้ใน CSV)
    path: str  # path ต่อจาก BASE_URL
    sector_style: Optional[str]  # "standard" / "non_sector" / None (= ไม่ส่ง year/sector)
    aggregate: str  # "last" (ใช้แถวสุดท้าย) หรือ "sum" (รวมทุกแถว)
    fields: Dict[str, str] = field(default_factory=dict)  # metric -> ชื่อฟิลด์ใน JSON

    @property
    def uses_year(self) -> bool:
        return self.sector_style is not None


ENDPOINTS = (
    EndpointSpec(
        category="coop",
        name="GetCoopOracleCountNEW",
        path="api/CoopProfile/GetCoopOracleCountNEW",
        sector_style=None,  # หน้าเว็บไม่ได้ส่ง year/sector ไป
        aggregate="last",  # loop เขียนทับ -> ค่าจากแถวสุดท้าย
        fields={"total": "coopCount", "active": "active", "non_active": "nonActive"},
    ),
    EndpointSpec(
        category="member",
        name="GetCoopSumMemberNew",
        path="api/Member/GetCoopSumMemberNew",
        sector_style="standard",
        aggregate="sum",
        fields={"male": "dataM", "female": "dataFm", "total": "sum"},
    ),
    EndpointSpec(
        category="committee",
        name="GetCoopSumCommitteeNew",
        path="api/CoopCommittee/GetCoopSumCommitteeNew",
        sector_style="standard",
        aggregate="sum",
        fields={"male": "dataM", "female": "dataFm", "total": "sum"},
    ),
    EndpointSpec(
        category="officer",
        name="GetCoopSumOfficer",
        path="api/ProfileData/GetCoopSumOfficer",
        sector_style="non_sector",
        aggregate="sum",
        fields={"male": "dataM", "female": "dataFm", "total": "sum"},
    ),
)

ENDPOINTS_BY_CATEGORY = {spec.category: spec for spec in ENDPOINTS}

# ลำดับคอลัมน์ของไฟล์ wide
WIDE_COLUMNS = [
    "coop_total", "coop_active", "coop_non_active",
    "member_male", "member_female", "member_total",
    "committee_male", "committee_female", "committee_total",
    "officer_male", "officer_female", "officer_total",
]
