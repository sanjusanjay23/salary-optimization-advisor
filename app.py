"""
app.py — Main Flask Application
--------------------------------
Salary Optimization Advisor
Authors: Chidvilash Yeccharla & Sanjay

Routes:
  GET  /           → input form (index.html)
  POST /analyze    → process form, parse resume, fetch salary data, run LLM
  GET  /results    → display report (results.html)
  GET  /health     → health check
"""

import os
import time
import uuid

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from utils.resume_parser  import parse_resume
from utils.salary_scraper import get_salary_data, calculate_percentile
from utils.llm_analyzer   import analyze_with_llm

# ── App setup ──────────────────────────────────────────────────────────────
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(32)
app.config["MAX_CONTENT_LENGTH"] = 21 * 1024 * 1024  # reject oversized uploads early

# Upload config
ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILE_SIZE_MB   = 20


# Reports are kept server-side: a full report is larger than the 4 KB
# browser cookie limit, so the cookie session only stores a report ID.
REPORT_TTL_SECONDS = 60 * 60
_reports: dict[str, tuple[float, dict]] = {}


def save_report(data: dict) -> str:
    now = time.time()
    for key in [k for k, (ts, _) in _reports.items() if now - ts > REPORT_TTL_SECONDS]:
        _reports.pop(key, None)
    report_id = uuid.uuid4().hex
    _reports[report_id] = (now, data)
    return report_id


def load_report(report_id: str | None) -> dict | None:
    entry = _reports.get(report_id or "")
    if not entry or time.time() - entry[0] > REPORT_TTL_SECONDS:
        return None
    return entry[1]


@app.template_filter("ordinal")
def ordinal(value) -> str:
    """1 -> 1st, 2 -> 2nd, 23 -> 23rd, 11 -> 11th."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Render the main input form."""
    return render_template("index.html")


@app.route("/health")
def health():
    return {"status": "ok", "app": "Salary Optimization Advisor"}, 200


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Main processing route.
    1. Validate form inputs
    2. Parse PDF resume with PyPDF2
    3. Fetch salary market data (BLS API -> H1B filings -> estimates)
    4. Send everything to the LLM (gpt-oss-120b via Groq)
    5. Store report in session, redirect to /results
    """

    # ── 1. Collect and validate form data ──
    job_title      = request.form.get("job_title", "").strip()
    location       = request.form.get("location", "").strip()
    current_salary = request.form.get("current_salary", "").strip()
    years_exp      = request.form.get("years_exp", "").strip()
    education      = request.form.get("education", "bachelor")
    industry       = request.form.get("industry", "").strip()
    skills_text    = request.form.get("skills", "").strip()

    # Required fields
    if not job_title:
        flash("Job title is required.", "error")
        return redirect(url_for("index"))

    if not location:
        flash("Location is required.", "error")
        return redirect(url_for("index"))

    if not current_salary:
        flash("Current salary is required.", "error")
        return redirect(url_for("index"))

    # Parse salary to integer
    try:
        salary_int = int(current_salary.replace(",", "").replace("$", "").strip())
        if salary_int < 10000 or salary_int > 5000000:
            raise ValueError("Out of range")
    except ValueError:
        flash("Please enter a valid salary (e.g. 95000 or 95,000).", "error")
        return redirect(url_for("index"))

    # ── 2. Parse resume PDF (PyPDF2) ──
    resume_text     = ""
    resume_keywords = {}

    resume_file = request.files.get("resume")
    if resume_file and resume_file.filename:
        if not allowed_file(resume_file.filename):
            flash("Only PDF resumes are accepted.", "error")
            return redirect(url_for("index"))

        # Check file size
        resume_file.seek(0, 2)          # seek to end
        file_size_mb = resume_file.tell() / (1024 * 1024)
        resume_file.seek(0)             # reset to start

        if file_size_mb > MAX_FILE_SIZE_MB:
            flash(f"Resume file must be under {MAX_FILE_SIZE_MB}MB.", "error")
            return redirect(url_for("index"))

        parse_result = parse_resume(resume_file)
        if parse_result["success"]:
            resume_text     = parse_result["raw_text"]
            resume_keywords = parse_result["keywords"]
        else:
            # Non-fatal: warn but continue without resume
            flash(
                f"Could not read resume PDF ({parse_result['error']}). "
                "Analysis will continue using your profile details only.",
                "warning"
            )

    # ── 3. Fetch salary market data (BLS API -> H1B filings -> estimates) ──
    try:
        salary_data = get_salary_data(job_title, location)
        percentile  = calculate_percentile(salary_int, salary_data)
    except Exception as e:
        # Non-fatal: use fallback
        salary_data = {
            "p25": round(salary_int * 0.75),
            "median": round(salary_int * 1.05),
            "p75":  round(salary_int * 1.30),
            "p90":  round(salary_int * 1.55),
            "source": "Estimated (salary lookup failed)",
            "source_type": "estimate",
        }
        percentile = 45
        print(f"[app] Salary lookup error (using fallback): {e}")

    # ── 4. Run LLM analysis (Groq API) ──
    try:
        report = analyze_with_llm(
            job_title       = job_title,
            location        = location,
            current_salary  = salary_int,
            years_exp       = years_exp,
            education       = education,
            industry        = industry,
            skills_text     = skills_text,
            resume_text     = resume_text,
            resume_keywords = resume_keywords,
            salary_data     = salary_data,
            percentile      = percentile,
        )
    except ValueError as e:
        flash(f"Analysis error: {str(e)}", "error")
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"Unexpected error during analysis: {str(e)}", "error")
        return redirect(url_for("index"))

    # ── 5. Store report server-side and redirect ──
    session["report_id"] = save_report({
        "report": report,
        "form": {
            "job_title":      job_title,
            "location":       location,
            "current_salary": salary_int,
            "years_exp":      years_exp,
            "education":      education,
            "industry":       industry,
            "has_resume":     bool(resume_text),
        },
    })

    return redirect(url_for("results"))


@app.errorhandler(413)
def file_too_large(_error):
    flash(f"Resume file must be under {MAX_FILE_SIZE_MB}MB.", "error")
    return redirect(url_for("index"))


@app.route("/results")
def results():
    """Display the analysis report."""
    data = load_report(session.get("report_id"))

    if not data:
        flash("No report found. Please run a new analysis.", "error")
        return redirect(url_for("index"))

    return render_template("results.html", report=data["report"], form=data["form"])


# ── Run ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port  = int(os.getenv("PORT", "5000"))
    print("\n" + "=" * 55)
    print("  Salary Optimization Advisor")
    print(f"  Running at:  http://127.0.0.1:{port}")
    print("=" * 55 + "\n")
    app.run(debug=debug, port=port)
