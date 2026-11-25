import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


SAMPLE_SALARY = {
    "p25": 105210,
    "median": 135980,
    "p75": 171980,
    "p90": 214670,
    "source": "BLS OEWS Official Data 2025 (SOC 15-1252)",
    "source_type": "government_api",
}


def make_report(salary_data=None, percentile=10):
    """A report shaped exactly like the LLM JSON schema in llm_analyzer.py."""
    return {
        "summary_headline": "You are paid below market for your role.",
        "market_context": "Demand for software engineers remains strong.",
        "percentile_analysis": "You sit near the bottom of the market range.",
        "resume_strengths": ["Python", "Flask", "APIs", "Testing"],
        "skill_gaps": [
            {"skill": "AWS", "impact": "high", "salary_boost": "$8,000-$15,000", "how_to_learn": "AWS course"},
            {"skill": "Docker", "impact": "medium", "salary_boost": "$5,000-$10,000", "how_to_learn": "Docker course"},
            {"skill": "SQL", "impact": "medium", "salary_boost": "$3,000-$7,000", "how_to_learn": "SQL course"},
            {"skill": "Leadership", "impact": "low", "salary_boost": "$2,000-$5,000", "how_to_learn": "Course"},
        ],
        "resume_improvement_tips": ["Add metrics", "Add links", "Tailor keywords", "Shorten"],
        "certifications_to_pursue": [
            {"name": "AWS SAA", "provider": "AWS", "salary_impact": "$5,000-$10,000", "timeline": "3 months"},
            {"name": "CKA", "provider": "CNCF", "salary_impact": "$5,000-$10,000", "timeline": "4 months"},
            {"name": "Terraform", "provider": "HashiCorp", "salary_impact": "$3,000-$6,000", "timeline": "2 months"},
        ],
        "action_plan": [
            {"step": i, "title": f"Step {i}", "description": "Do it", "timeline": "1-2 months",
             "salary_impact": "$1,000-$2,000", "priority": "high"}
            for i in range(1, 5)
        ],
        "potential_salary": 125000,
        "alternative_titles": [
            {"title": f"Role {i}", "salary_range": "$100,000-$140,000", "match_pct": 80} for i in range(4)
        ],
        "negotiation_tips": ["Anchor high", "Use data", "Mention offers", "Be patient"],
        "top_companies": ["A", "B", "C", "D", "E", "F"],
        "salary_data": salary_data or dict(SAMPLE_SALARY),
        "percentile": percentile,
    }


@pytest.fixture
def client(monkeypatch):
    import app as app_module

    app_module.app.config.update(TESTING=True)
    app_module._reports.clear()
    with app_module.app.test_client() as client:
        yield client
