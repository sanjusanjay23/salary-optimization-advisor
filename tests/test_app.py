import io

import app as app_module
from tests.conftest import SAMPLE_SALARY, make_report

VALID_FORM = {
    "job_title": "Software Engineer",
    "location": "Boston, MA",
    "current_salary": "$85,000",
    "years_exp": "2",
    "education": "master",
    "industry": "SaaS",
    "skills": "Python, Flask",
}


def mock_pipeline(monkeypatch):
    calls = {}

    def fake_llm(**kwargs):
        calls.update(kwargs)
        return make_report(kwargs["salary_data"], kwargs["percentile"])

    monkeypatch.setattr(app_module, "get_salary_data", lambda title, loc: dict(SAMPLE_SALARY))
    monkeypatch.setattr(app_module, "analyze_with_llm", fake_llm)
    return calls


def test_index_and_health(client):
    assert client.get("/").status_code == 200
    resp = client.get("/health")
    assert resp.status_code == 200 and resp.get_json()["status"] == "ok"


def test_missing_job_title_redirects_with_error(client):
    resp = client.post("/analyze", data={**VALID_FORM, "job_title": ""}, follow_redirects=True)
    assert b"Job title is required" in resp.data


def test_invalid_salary_rejected(client):
    resp = client.post("/analyze", data={**VALID_FORM, "current_salary": "lots"}, follow_redirects=True)
    assert b"valid salary" in resp.data


def test_non_pdf_resume_rejected(client):
    data = {**VALID_FORM, "resume": (io.BytesIO(b"hello"), "resume.docx")}
    resp = client.post("/analyze", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert b"Only PDF resumes" in resp.data


def test_full_analysis_renders_results(client, monkeypatch):
    calls = mock_pipeline(monkeypatch)

    resp = client.post("/analyze", data=VALID_FORM)
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/results")

    page = client.get("/results")
    assert page.status_code == 200
    assert b"You are paid below market" in page.data
    # "$85,000" is sanitized to an integer before analysis
    assert calls["current_salary"] == 85000
    # 85,000 / 105,210 (p25) * 25 -> 20th percentile
    assert calls["percentile"] == 20


def test_report_is_stored_server_side_not_in_cookie(client, monkeypatch):
    mock_pipeline(monkeypatch)
    resp = client.post("/analyze", data=VALID_FORM)

    cookies = " ".join(resp.headers.getlist("Set-Cookie"))
    # A full report is ~4 KB+; only a small signed report ID should be in the cookie
    assert len(cookies) < 500
    assert len(app_module._reports) == 1


def test_results_without_report_redirects(client):
    resp = client.get("/results", follow_redirects=True)
    assert b"No report found" in resp.data


def test_llm_error_is_shown_to_user(client, monkeypatch):
    monkeypatch.setattr(app_module, "get_salary_data", lambda title, loc: dict(SAMPLE_SALARY))

    def boom(**kwargs):
        raise ValueError("GROQ_API_KEY is not set in your .env file.")

    monkeypatch.setattr(app_module, "analyze_with_llm", boom)
    resp = client.post("/analyze", data=VALID_FORM, follow_redirects=True)
    assert b"GROQ_API_KEY is not set" in resp.data


def test_ordinal_filter():
    numbers = (1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 99)
    assert [app_module.ordinal(n) for n in numbers] == ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "23rd", "99th"]
