from unittest.mock import MagicMock

import pytest

from utils import salary_scraper as ss


@pytest.fixture(autouse=True)
def clear_cache():
    ss._bls_cache.clear()
    yield
    ss._bls_cache.clear()


def bls_response(values, year="2025"):
    """Fake BLS API JSON for the four percentile series of SOC 15-1252."""
    series = []
    for key, value in values.items():
        sid = ss._bls_series_id("15-1252", ss.BLS_DATATYPES[key])
        series.append({"seriesID": sid, "data": [{"year": year, "value": value}]})
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"status": "REQUEST_SUCCEEDED", "Results": {"series": series}}
    return resp


def test_series_id_has_official_25_char_format():
    sid = ss._bls_series_id("15-1252", "13")
    assert sid == "OEUN000000000000015125213"
    assert len(sid) == 25


def test_match_bls_code():
    assert ss._match_bls_code("Senior Software Engineer") == "15-1252"
    assert ss._match_bls_code("Data Scientist II") == "15-2051"
    assert ss._match_bls_code("Chef") is None


def test_bls_returns_real_percentiles(monkeypatch):
    post = MagicMock(return_value=bls_response(
        {"p25": "105210", "median": "135980", "p75": "171980", "p90": "214670"}))
    monkeypatch.setattr(ss.requests, "post", post)

    result = ss._fetch_bls_salary("Software Engineer")

    assert (result["p25"], result["median"], result["p75"], result["p90"]) == (105210, 135980, 171980, 214670)
    assert result["source_type"] == "government_api"
    assert "2025" in result["source"]


def test_bls_handles_top_coded_p90(monkeypatch):
    # BLS reports "-" when a wage is above its reporting ceiling
    monkeypatch.setattr(ss.requests, "post", MagicMock(return_value=bls_response(
        {"p25": "100000", "median": "130000", "p75": "170000", "p90": "-"})))

    result = ss._fetch_bls_salary("Software Engineer")

    assert result["p90"] == round(170000 * 1.2)


def test_bls_results_are_cached(monkeypatch):
    post = MagicMock(return_value=bls_response(
        {"p25": "100000", "median": "130000", "p75": "170000", "p90": "200000"}))
    monkeypatch.setattr(ss.requests, "post", post)

    ss._fetch_bls_salary("Software Engineer")
    ss._fetch_bls_salary("Backend Developer")  # same SOC code

    assert post.call_count == 1


def test_bls_sends_registration_key_when_set(monkeypatch):
    post = MagicMock(return_value=bls_response(
        {"p25": "100000", "median": "130000", "p75": "170000", "p90": "200000"}))
    monkeypatch.setattr(ss.requests, "post", post)
    monkeypatch.setenv("BLS_API_KEY", "test-key")

    ss._fetch_bls_salary("Software Engineer")

    assert post.call_args.kwargs["json"]["registrationkey"] == "test-key"


def test_bls_rate_limited_returns_none(monkeypatch):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"status": "REQUEST_NOT_PROCESSED", "Results": {}}
    monkeypatch.setattr(ss.requests, "post", MagicMock(return_value=resp))

    assert ss._fetch_bls_salary("Software Engineer") is None


def test_get_salary_data_falls_back_when_all_sources_fail(monkeypatch):
    monkeypatch.setattr(ss, "_fetch_bls_salary", lambda title: None)
    monkeypatch.setattr(ss, "_fetch_h1b_salary", lambda title, loc: None)
    monkeypatch.setattr(ss.time, "sleep", lambda s: None)

    result = ss.get_salary_data("Software Engineer", "Boston, MA")

    assert result["source_type"] == "estimate"
    # Callers must not be able to mutate the shared fallback table
    result["median"] = 1
    assert ss.FALLBACK_DATA["software_engineer"]["median"] != 1


@pytest.mark.parametrize("salary, expected", [
    (105210, 25),   # exactly p25
    (135980, 50),   # exactly median
    (171980, 75),   # exactly p75
    (214670, 90),   # exactly p90
])
def test_percentile_at_markers(salary, expected):
    data = {"p25": 105210, "median": 135980, "p75": 171980, "p90": 214670}
    assert ss.calculate_percentile(salary, data) == expected


def test_percentile_is_monotonic_and_bounded():
    data = {"p25": 100000, "median": 130000, "p75": 170000, "p90": 200000}
    values = [ss.calculate_percentile(s, data) for s in range(10000, 1000000, 5000)]
    assert values == sorted(values)
    assert min(values) >= 5 and max(values) <= 99
