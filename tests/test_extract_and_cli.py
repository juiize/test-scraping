import csv

import pytest

from cpd_scraper import config
from cpd_scraper.cli import parse_args, run
from cpd_scraper.client import ApiError, normalize_rows
from cpd_scraper.extract import build_params

from conftest import EXPECTED, FakeClient


# ---------- query string ----------

@pytest.mark.parametrize("code,expected", [("0", "0"), ("1", "1"), ("2", "2")])
def test_standard_sector_params(code, expected):
    spec = config.ENDPOINTS_BY_CATEGORY["member"]
    assert build_params(spec, 2568, code) == {"year": "2568", "sector": expected}


@pytest.mark.parametrize("code,expected", [
    ("0", "null"), ("1", "สหกรณ์ภาคการเกษตร"), ("2", "สหกรณ์นอกภาคการเกษตร"),
])
def test_officer_uses_non_sector_params(code, expected):
    spec = config.ENDPOINTS_BY_CATEGORY["officer"]
    assert build_params(spec, 2568, code) == {"year": "2568", "sector": expected}


def test_coop_has_no_params():
    assert build_params(config.ENDPOINTS_BY_CATEGORY["coop"], 2568, "0") is None


def test_default_year_is_previous_be_year():
    from datetime import datetime
    assert config.default_data_year(datetime(2026, 10, 29, tzinfo=config.TZ_BANGKOK)) == 2568


# ---------- normalize ----------

def test_normalize_rows_variants():
    assert normalize_rows(None) == []
    assert normalize_rows([{"a": 1}, "x"]) == [{"a": 1}]
    assert normalize_rows({"a": 1}) == [{"a": 1}]
    assert normalize_rows({"data": [{"a": 1}]}) == [{"a": 1}]
    with pytest.raises(ApiError):
        normalize_rows("text")


# ---------- CLI end-to-end (ไม่ยิงเน็ตจริง) ----------

def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_run_default_writes_expected_csv(tmp_path, fake_client):
    out = tmp_path / "out.csv"
    args = parse_args(["--year", "2568", "--out", str(out), "--wide"])
    assert run(args, client=fake_client) == 0

    rows = read_csv(out)
    assert len(rows) == 12  # 4 กลุ่ม x 3 metric
    got = {(r["category"], r["metric"]): int(r["value"]) for r in rows}
    for category, metrics in EXPECTED.items():
        for metric, value in metrics.items():
            assert got[(category, metric)] == value

    officer = [r for r in rows if r["category"] == "officer"]
    assert {r["data_year"] for r in officer} == {"2568"}
    assert {r["sector"] for r in officer} == {"ทั้งหมด"}
    coop = [r for r in rows if r["category"] == "coop"]
    assert {r["data_year"] for r in coop} == {""}

    wide = read_csv(tmp_path / "out_wide.csv")
    assert len(wide) == 1
    assert wide[0]["officer_total"] == "32194"
    assert wide[0]["coop_total"] == "7563"

    # BOM ต้นไฟล์ (ให้ Excel อ่านไทยได้)
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")


def test_append_keeps_single_header_and_bom(tmp_path, fake_client):
    out = tmp_path / "out.csv"
    args = parse_args(["--out", str(out)])
    run(args, client=fake_client)
    run(args, client=fake_client)
    data = out.read_bytes()
    assert data.count(b"\xef\xbb\xbf") == 1
    assert data.decode("utf-8-sig").count("scraped_at,data_year") == 1
    assert len(read_csv(out)) == 24


def test_all_years_all_sectors_call_count(tmp_path, fake_client):
    args = parse_args(["--all-years", "--sector", "all", "--out", str(tmp_path / "o.csv")])
    run(args, client=fake_client)
    n_years = len(args.years)
    # coop 1 ครั้ง + (ปี x 3 ภาค x 3 endpoint)
    assert len(fake_client.calls) == 1 + n_years * 3 * 3
    assert args.years[0] == config.default_data_year()
    assert args.years[-1] == config.FIRST_YEAR


def test_partial_failure_returns_1_and_writes_rest(tmp_path):
    client = FakeClient(fail_paths={"api/ProfileData/GetCoopSumOfficer"})
    out = tmp_path / "o.csv"
    assert run(parse_args(["--out", str(out)]), client=client) == 1
    cats = {r["category"] for r in read_csv(out)}
    assert cats == {"coop", "member", "committee"}


def test_all_failures_returns_2_and_no_file(tmp_path):
    client = FakeClient(fail_paths=set(p.path for p in config.ENDPOINTS))
    out = tmp_path / "o.csv"
    assert run(parse_args(["--out", str(out)]), client=client) == 2
    assert not out.exists()


def test_save_raw_writes_json(tmp_path, fake_client):
    raw = tmp_path / "raw"
    run(parse_args(["--out", str(tmp_path / "o.csv"), "--save-raw", str(raw)]), client=fake_client)
    files = sorted(p.name for p in raw.glob("*.json"))
    assert len(files) == 4
    assert any("GetCoopSumOfficer_" in f for f in files)
