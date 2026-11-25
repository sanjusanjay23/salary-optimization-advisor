import io

from utils.resume_parser import extract_keywords, parse_resume


def test_short_keywords_do_not_match_inside_words():
    kw = extract_keywords("Good career growth, strong program management and governance.")
    assert "r" not in kw["skills"]
    assert "go" not in kw["skills"]


def test_detects_real_skills_including_symbols():
    text = "Skills: Python, C++, C#, Node.js, Go, R, CI/CD, AWS, Docker, machine learning"
    skills = extract_keywords(text)["skills"]
    for expected in ["python", "c++", "c#", "node.js", "go", "r", "ci/cd", "aws", "docker", "machine learning"]:
        assert expected in skills


def test_c_plus_plus_does_not_count_as_c_sharp():
    skills = extract_keywords("I write C++ every day")["skills"]
    assert "c++" in skills and "c#" not in skills


def test_years_of_experience_extraction():
    kw = extract_keywords("Software engineer with 5+ years of professional experience. 2 yrs exp in Go.")
    assert kw["years_of_experience"] == 5


def test_education_and_certifications():
    kw = extract_keywords("M.S. in Artificial Intelligence. AWS Certified Cloud Practitioner.")
    assert "artificial intelligence" in kw["education"]
    assert "aws certified" in kw["certifications"]


def test_invalid_pdf_fails_gracefully():
    result = parse_resume(io.BytesIO(b"this is not a pdf"))
    assert result["success"] is False
    assert result["raw_text"] == ""
