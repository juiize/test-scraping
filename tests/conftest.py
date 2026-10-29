import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cpd_scraper import config  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"

SECTION_BY_PATH = {s.path: s.key for s in config.SECTIONS}

# ตัวเลขบนหน้าเว็บ (ภาพ CPD.jpg, ข้อมูล ณ ปี 2568)
EXPECTED = {
    "coop": {"total": 7563, "active": 6316, "non_active": 1247},
    "member": {"male": 5828231, "female": 5084460, "total": 10912691},
    "committee": {"male": 36599, "female": 27188, "total": 63787},
    "officer": {"male": 11154, "female": 21040, "total": 32194},
}


def load_fixture(key):
    return json.loads((FIXTURES / f"{key}.json").read_text(encoding="utf-8"))


class FakeClient:
    """แทน CpdClient โดยคืนค่าจาก fixture และจดว่าเรียกอะไรไปบ้าง"""

    def __init__(self, fail_paths=()):
        self.calls = []
        self.fail_paths = set(fail_paths)

    def post(self, path, params=None, body=None):
        from cpd_scraper.client import ApiError

        self.calls.append((path, dict(params or {}), dict(body or {})))
        if path in self.fail_paths:
            raise ApiError(f"HTTP 500 จาก {path}")
        data = load_fixture(SECTION_BY_PATH[path])
        if isinstance(data, dict):  # oae_detail แยกตาม groupCode
            data = data[body["groupCode"]]
        query = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        url = f"https://example.test/{path}" + (f"?{query}" if query else "")
        return data, url


@pytest.fixture
def fake_client():
    return FakeClient()
