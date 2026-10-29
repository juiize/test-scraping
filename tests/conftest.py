import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIXTURES = ROOT / "tests" / "fixtures"

FIXTURE_BY_PATH = {
    "api/CoopProfile/GetCoopOracleCountNEW": "coop_count.json",
    "api/Member/GetCoopSumMemberNew": "member_sum.json",
    "api/CoopCommittee/GetCoopSumCommitteeNew": "committee_sum.json",
    "api/ProfileData/GetCoopSumOfficer": "officer_sum.json",
}

# ตัวเลขบนหน้าเว็บ (ภาพ CPD.jpg, ข้อมูล ณ ปี 2568)
EXPECTED = {
    "coop": {"total": 7563, "active": 6316, "non_active": 1247},
    "member": {"male": 5828231, "female": 5084460, "total": 10912691},
    "committee": {"male": 36599, "female": 27188, "total": 63787},
    "officer": {"male": 11154, "female": 21040, "total": 32194},
}


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeClient:
    """แทน CpdClient โดยคืนค่าจาก fixture และจดว่าเรียกอะไรไปบ้าง"""

    def __init__(self, fail_paths=()):
        self.calls = []
        self.fail_paths = set(fail_paths)

    def post(self, path, params=None, body=None):
        from cpd_scraper.client import ApiError

        self.calls.append((path, params))
        if path in self.fail_paths:
            raise ApiError(f"HTTP 500 จาก {path}")
        query = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        url = f"https://example.test/{path}" + (f"?{query}" if query else "")
        return load_fixture(FIXTURE_BY_PATH[path]), url


@pytest.fixture
def fake_client():
    return FakeClient()
