import pytest

from cpd_scraper import config
from cpd_scraper.transform import SchemaError, aggregate, flatten_row, get_field, to_int, validate

from conftest import EXPECTED, load_fixture


@pytest.mark.parametrize("spec", config.SUMMARIES, ids=lambda s: s.category)
def test_aggregate_matches_screenshot(spec):
    rows = load_fixture(spec.section)
    assert aggregate(spec, rows) == EXPECTED[spec.category]


def test_coop_uses_last_row_not_sum():
    spec = config.SUMMARIES_BY_CATEGORY["coop"]
    rows = [{"coopCount": 100, "active": 90, "nonActive": 10},
            {"coopCount": 7563, "active": 6316, "nonActive": 1247}]
    assert aggregate(spec, rows)["total"] == 7563


def test_empty_response_gives_zeros():
    spec = config.SUMMARIES_BY_CATEGORY["officer"]
    assert aggregate(spec, []) == {"male": 0, "female": 0, "total": 0}


def test_pascal_case_fields_are_accepted():
    spec = config.SUMMARIES_BY_CATEGORY["officer"]
    rows = [{"DataM": 1, "DataFm": 2, "Sum": 3}]
    assert aggregate(spec, rows) == {"male": 1, "female": 2, "total": 3}


def test_missing_field_raises_helpful_error():
    spec = config.SUMMARIES_BY_CATEGORY["officer"]
    with pytest.raises(SchemaError) as exc:
        aggregate(spec, [{"male": 1, "female": 2, "total": 3}])
    assert "dataM" in str(exc.value)
    assert "ฟิลด์ที่มี" in str(exc.value)


def test_null_values_count_as_zero():
    spec = config.SUMMARIES_BY_CATEGORY["member"]
    rows = [{"dataM": None, "dataFm": 5, "sum": 5}, {"dataM": 1, "dataFm": None, "sum": 1}]
    assert aggregate(spec, rows) == {"male": 1, "female": 5, "total": 6}


@pytest.mark.parametrize("raw,expected", [
    (None, 0), ("", 0), (12, 12), (12.0, 12), ("1,234", 1234), (" 56 ", 56), ("7.0", 7),
])
def test_to_int(raw, expected):
    assert to_int(raw) == expected


def test_to_int_rejects_text():
    with pytest.raises(ValueError):
        to_int("abc")


def test_get_field_case_insensitive():
    assert get_field({"CoopCount": 5}, "coopCount") == 5


@pytest.mark.parametrize("category", ["coop", "member", "committee", "officer"])
def test_validate_passes_for_screenshot_numbers(category):
    assert validate(category, EXPECTED[category]) == []


def test_validate_reports_mismatch():
    msgs = validate("officer", {"male": 1, "female": 1, "total": 3})
    assert len(msgs) == 1 and "officer" in msgs[0]


def test_flatten_row_nested_and_lists():
    row = {"a": 1, "b": {"c": 2, "d": {"e": 3}}, "l": [1, "ไทย"], "n": None}
    assert flatten_row(row) == {"a": 1, "b.c": 2, "b.d.e": 3, "l": '[1, "ไทย"]', "n": ""}
