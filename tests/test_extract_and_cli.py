import csv

import pytest

from cpd_scraper import config
from cpd_scraper.cli import main, parse_args, run
from cpd_scraper.client import ApiError, normalize_rows
from cpd_scraper.extract import build_params

from conftest import EXPECTED, FakeClient, load_fixture

S = config.SECTIONS_BY_KEY
DEFAULT_KEYS = [s.key for s in config.SECTIONS if s.default]


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


# ---------- query string (ตรงกับ callable.ts) ----------

@pytest.mark.parametrize("code,expected", [("0", "0"), ("1", "1"), ("2", "2")])
def test_standard_sector_params(code, expected):
    assert build_params(S["member_sum"], 2568, code) == {"year": "2568", "sector": expected}


@pytest.mark.parametrize("code,expected", [
    ("0", "null"), ("1", "สหกรณ์ภาคการเกษตร"), ("2", "สหกรณ์นอกภาคการเกษตร"),
])
def test_officer_uses_non_sector_params(code, expected):
    assert build_params(S["officer_sum"], 2568, code) == {"year": "2568", "sector": expected}


def test_year_change_key_for_finance_business():
    for key in ("finance", "finance_type", "business", "business_type",
                "participation", "participation_type", "oae_group", "oae_detail", "rubber"):
        assert build_params(S[key], 2568, "1") == {"year_change": "2568", "sector": "1"}, key


def test_no_params_for_coop_count_and_map_coop():
    assert build_params(S["coop_count"], None, None) is None
    assert build_params(S["map_coop_province"], None, None) is None


def test_defect_sector_only():
    assert build_params(S["defect_province"], None, "2") == {"sector": "2"}


def test_default_year_is_previous_be_year():
    from datetime import datetime
    assert config.default_data_year(datetime(2026, 10, 29, tzinfo=config.TZ_BANGKOK)) == 2568


def test_normalize_rows_variants():
    assert normalize_rows(None) == []
    assert normalize_rows([{"a": 1}, "x"]) == [{"a": 1}]
    assert normalize_rows({"a": 1}) == [{"a": 1}]
    assert normalize_rows({"data": [{"a": 1}]}) == [{"a": 1}]
    with pytest.raises(ApiError):
        normalize_rows("text")


# ---------- เรียก API ----------

def test_default_run_calls_every_default_section_once(tmp_path, fake_client):
    run(parse_args(["--out-dir", str(tmp_path)]), client=fake_client)
    paths = [c[0] for c in fake_client.calls]
    # oae_detail เรียก 3 ครั้ง (groupCode 1,2,3) ที่เหลือ 1 ครั้ง
    assert len(paths) == len(DEFAULT_KEYS) + 2
    assert S["defect_province"].path not in paths
    groups = sorted(c[2]["groupCode"] for c in fake_client.calls if c[0] == S["oae_detail"].path)
    assert groups == ["1", "2", "3"]
    for _, _, body in fake_client.calls:
        assert body["OrgOrgId"] == body["PhakId"] == body["KhetId"] == "null"


def test_all_years_all_sectors_dedupes_static_sections(tmp_path, fake_client):
    args = parse_args(["--all-years", "--sector", "all", "--out-dir", str(tmp_path)])
    run(args, client=fake_client)
    n_years = len(args.years)
    static = [s for s in args.section_specs if not s.uses_year and not s.uses_sector]
    dynamic = [s for s in args.section_specs if s.uses_year and s.uses_sector]
    assert len(static) + len(dynamic) == len(args.section_specs)
    expected = sum(len(s.body_variants) for s in static) + \
        n_years * 3 * sum(len(s.body_variants) for s in dynamic)
    assert len(fake_client.calls) == expected
    assert args.years[0] == config.default_data_year() and args.years[-1] == config.FIRST_YEAR


def test_sections_option_and_unknown(tmp_path, fake_client):
    args = parse_args(["--sections", "officer_sum,finance", "--out-dir", str(tmp_path)])
    run(args, client=fake_client)
    assert [c[0] for c in fake_client.calls] == [S["officer_sum"].path, S["finance"].path]
    with pytest.raises(SystemExit):
        parse_args(["--sections", "nope"])


def test_sections_all_includes_defect():
    keys = [s.key for s in parse_args(["--sections", "all"]).section_specs]
    assert "defect_province" in keys


def test_summary_only(tmp_path, fake_client):
    run(parse_args(["--summary-only", "--out-dir", str(tmp_path)]), client=fake_client)
    assert len(fake_client.calls) == 4


# ---------- ไฟล์ output ----------

def test_outputs_default_run(tmp_path, fake_client):
    assert run(parse_args(["--year", "2568", "--out-dir", str(tmp_path)]), client=fake_client) == 0

    # ราย section: ครบทุกไฟล์ และมีทุกแถวจาก response
    for key in DEFAULT_KEYS:
        path = tmp_path / "sections" / f"{key}.csv"
        assert path.exists(), key
        rows = read_csv(path)
        fixture = load_fixture(key)
        n_expected = sum(len(v) for v in fixture.values()) if isinstance(fixture, dict) else len(fixture)
        assert len(rows) == n_expected, key

    prov = read_csv(tmp_path / "sections" / "map_coop_province.csv")
    assert prov[0]["provinceName"] == "กรุงเทพมหานคร" and prov[0]["active"] == "1000"
    assert prov[0]["data_year"] == "" and prov[0]["sector"] == ""

    officer = read_csv(tmp_path / "sections" / "officer_sum.csv")
    assert {r["data_year"] for r in officer} == {"2568"}
    assert {r["sector"] for r in officer} == {"ทั้งหมด"}
    assert [r["row_no"] for r in officer] == ["1", "2"]

    oae = read_csv(tmp_path / "sections" / "oae_detail.csv")
    assert {r["req_groupCode"] for r in oae} == {"1", "2", "3"}

    business = read_csv(tmp_path / "sections" / "business.csv")
    assert business[0]["business.deposit"] == "100.5"  # nested -> คอลัมน์ a.b

    # รวมทุกค่า
    long_rows = read_csv(tmp_path / "cpd_page_long.csv")
    assert {r["section"] for r in long_rows} == set(DEFAULT_KEYS)
    hit = [r for r in long_rows if r["section"] == "officer_sum" and r["field"] == "sum"]
    assert sorted(int(r["value"]) for r in hit) == [15194, 17000]

    # การ์ดสรุป
    summary = read_csv(tmp_path / "cpd_summary.csv")
    got = {(r["category"], r["metric"]): int(r["value"]) for r in summary}
    for category, metrics in EXPECTED.items():
        for metric, value in metrics.items():
            assert got[(category, metric)] == value
    wide = read_csv(tmp_path / "cpd_summary_wide.csv")
    assert wide[0]["officer_total"] == "32194" and wide[0]["coop_total"] == "7563"

    log = read_csv(tmp_path / "run_log.csv")
    assert len(log) == len(DEFAULT_KEYS) + 2 and {r["status"] for r in log} == {"ok"}

    assert (tmp_path / "cpd_summary.csv").read_bytes().startswith(b"\xef\xbb\xbf")


def test_append_keeps_single_header_and_bom(tmp_path, fake_client):
    args = parse_args(["--out-dir", str(tmp_path)])
    run(args, client=fake_client)
    run(args, client=fake_client)
    for name in ("cpd_summary.csv", "cpd_page_long.csv", "sections/officer_sum.csv"):
        data = (tmp_path / name).read_bytes()
        assert data.count(b"\xef\xbb\xbf") == 1, name
        assert data.decode("utf-8-sig").count("scraped_at,") == 1, name
    assert len(read_csv(tmp_path / "sections" / "officer_sum.csv")) == 4


def test_section_csv_merges_new_columns(tmp_path):
    from cpd_scraper.writer import write_section_csv
    path = tmp_path / "x.csv"
    write_section_csv(path, [{"scraped_at": "t1", "a": 1}])
    write_section_csv(path, [{"scraped_at": "t2", "a": 2, "b": 3}])
    rows = read_csv(path)
    assert rows == [{"scraped_at": "t1", "a": "1", "b": ""}, {"scraped_at": "t2", "a": "2", "b": "3"}]


def test_overwrite(tmp_path, fake_client):
    run(parse_args(["--out-dir", str(tmp_path)]), client=fake_client)
    run(parse_args(["--out-dir", str(tmp_path), "--overwrite"]), client=fake_client)
    assert len(read_csv(tmp_path / "sections" / "officer_sum.csv")) == 2


def test_partial_failure_returns_1_and_writes_rest(tmp_path):
    client = FakeClient(fail_paths={S["officer_sum"].path, S["finance"].path})
    assert run(parse_args(["--out-dir", str(tmp_path)]), client=client) == 1
    assert not (tmp_path / "sections" / "officer_sum.csv").exists()
    assert (tmp_path / "sections" / "member_sum.csv").exists()
    cats = {r["category"] for r in read_csv(tmp_path / "cpd_summary.csv")}
    assert cats == {"coop", "member", "committee"}
    errors = [r for r in read_csv(tmp_path / "run_log.csv") if r["status"] == "error"]
    assert {r["section"] for r in errors} == {"officer_sum", "finance"}


def test_all_failures_returns_2(tmp_path):
    client = FakeClient(fail_paths={s.path for s in config.SECTIONS})
    assert run(parse_args(["--out-dir", str(tmp_path)]), client=client) == 2
    assert not (tmp_path / "sections").exists()
    assert (tmp_path / "run_log.csv").exists()


def test_save_raw_writes_json(tmp_path, fake_client):
    run(parse_args(["--out-dir", str(tmp_path), "--save-raw"]), client=fake_client)
    files = sorted(p.name for p in (tmp_path / "raw").glob("*.json"))
    assert len(files) == len(DEFAULT_KEYS) + 2
    assert any("oae_detail" in f and "groupCode3" in f for f in files)


def test_list_sections(capsys):
    assert main(["--list-sections"]) == 0
    out = capsys.readouterr().out
    for s in config.SECTIONS:
        assert s.key in out
