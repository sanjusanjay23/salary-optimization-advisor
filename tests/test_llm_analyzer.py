import json
from unittest.mock import MagicMock

import pytest

from utils import llm_analyzer
from utils.llm_analyzer import build_prompt, parse_llm_json
from tests.conftest import SAMPLE_SALARY, make_report


def test_parse_plain_json():
    assert parse_llm_json('{"a": 1}') == {"a": 1}


def test_parse_json_inside_markdown_fence_and_chatter():
    raw = 'Here is your report:\n```json\n{"summary_headline": "Hi", "n": [1, 2]}\n```\nThanks!'
    assert parse_llm_json(raw) == {"summary_headline": "Hi", "n": [1, 2]}


@pytest.mark.parametrize("raw", ["no json here", '{"broken": ', "[1, 2, 3]"])
def test_parse_rejects_bad_output(raw):
    with pytest.raises(ValueError):
        parse_llm_json(raw)


def test_prompt_contains_profile_market_data_and_resume_keywords():
    prompt = build_prompt(
        job_title="Software Engineer", location="Boston, MA", current_salary=85000,
        years_exp="2", education="master", industry="SaaS", skills_text="Python",
        resume_text="", resume_keywords={"skills": ["python", "flask"]},
        salary_data=SAMPLE_SALARY, percentile=10,
    )
    assert "$85,000" in prompt
    assert "$135,980" in prompt
    assert "python, flask" in prompt
    assert "No resume provided" in prompt


def test_analyze_requires_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        llm_analyzer.analyze_with_llm("SE", "Boston", 85000, "2", "bachelor", "", "", "", {}, SAMPLE_SALARY, 10)


def test_analyze_calls_groq_and_attaches_salary_data(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    llm_json = {k: v for k, v in make_report().items() if k not in ("salary_data", "percentile")}
    message = MagicMock()
    message.choices = [MagicMock(message=MagicMock(content="```json\n" + json.dumps(llm_json) + "\n```"))]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = message
    monkeypatch.setattr(llm_analyzer, "Groq", lambda api_key: fake_client)

    report = llm_analyzer.analyze_with_llm(
        "Software Engineer", "Boston, MA", 85000, "2", "bachelor", "", "", "", {}, SAMPLE_SALARY, 10)

    kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == llm_analyzer.DEFAULT_MODEL
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["temperature"] == 0.3
    assert report["salary_data"] == SAMPLE_SALARY
    assert report["percentile"] == 10
    assert len(report["action_plan"]) == 4
