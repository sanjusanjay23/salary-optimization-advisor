"""
utils/resume_parser.py
----------------------
Extracts raw text from a PDF resume using PyPDF2.
Also runs basic keyword extraction for skills, education,
and experience sections to supplement LLM analysis.
"""

import re
import PyPDF2
import io

# ── Common tech / soft skill keywords to look for ──────────────────────────
SKILL_KEYWORDS = [
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "kotlin", "swift", "r", "scala", "matlab", "sql", "bash", "shell",
    # Web / frontend
    "react", "angular", "vue", "html", "css", "node.js", "express", "next.js",
    "django", "flask", "fastapi", "spring", "rails",
    # Data / ML / AI
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy",
    "spark", "hadoop", "data science", "statistics", "tableau", "power bi",
    # Cloud / DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd",
    "jenkins", "github actions", "linux",
    # Databases
    "mysql", "postgresql", "mongodb", "redis", "elasticsearch", "dynamodb",
    # Soft skills
    "leadership", "communication", "teamwork", "agile", "scrum", "project management",
]

EDUCATION_KEYWORDS = [
    "bachelor", "master", "phd", "doctorate", "b.s.", "m.s.", "b.e.", "m.e.",
    "b.tech", "m.tech", "mba", "associate", "diploma",
    "computer science", "engineering", "mathematics", "statistics",
    "information technology", "data science", "artificial intelligence",
]

CERT_KEYWORDS = [
    "aws certified", "google cloud", "azure certified", "pmp", "cissp",
    "tensorflow developer", "pytorch", "coursera", "udemy", "edx",
    "certification", "certified", "certificate",
]


def extract_text_from_pdf(file_storage) -> str:
    """
    Takes a Flask FileStorage object (uploaded PDF) and returns
    the full extracted text as a single string.
    """
    try:
        # Read into memory buffer — avoids saving to disk
        pdf_bytes = file_storage.read()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))

        full_text = []
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()
            if text:
                full_text.append(text.strip())

        extracted = "\n".join(full_text)

        if not extracted.strip():
            return "ERROR: Could not extract text from PDF. The file may be scanned/image-based."

        return extracted

    except Exception as e:
        return f"ERROR: Failed to parse PDF — {str(e)}"


def _contains_term(text_lower: str, term: str) -> bool:
    """
    Whole-term match, so short keywords like "r" or "go" don't match
    inside other words ("career", "good"). Works for terms with symbols
    such as "c++", "c#", "node.js" and "ci/cd".
    """
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9+#])"
    return re.search(pattern, text_lower) is not None


def extract_keywords(text: str) -> dict:
    """
    Scans the resume text for common skill/education keywords.
    Returns a dict with lists of found skills, education terms, certifications.
    This supplements the LLM — giving it a structured head start.
    """
    text_lower = text.lower()

    found_skills = [kw for kw in SKILL_KEYWORDS if _contains_term(text_lower, kw)]
    found_education = [kw for kw in EDUCATION_KEYWORDS if _contains_term(text_lower, kw)]
    found_certs = [kw for kw in CERT_KEYWORDS if _contains_term(text_lower, kw)]

    # Try to find years of experience mentions
    yoe_matches = re.findall(
        r'(\d+)\+?\s*(?:years?|yrs?)[\s\w]{0,20}(?:experience|exp)',
        text_lower
    )
    years_of_experience = max([int(y) for y in yoe_matches], default=None)

    return {
        "skills":             sorted(set(found_skills)),
        "education":          sorted(set(found_education)),
        "certifications":     sorted(set(found_certs)),
        "years_of_experience": years_of_experience,
    }


def parse_resume(file_storage) -> dict:
    """
    Master function: extracts text AND keywords from the uploaded resume PDF.
    Returns a dict with both the raw text and parsed keywords.
    """
    raw_text = extract_text_from_pdf(file_storage)

    if raw_text.startswith("ERROR"):
        return {
            "success":  False,
            "error":    raw_text,
            "raw_text": "",
            "keywords": {},
        }

    keywords = extract_keywords(raw_text)

    return {
        "success":  True,
        "raw_text": raw_text,
        "keywords": keywords,
    }
