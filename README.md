# Salary Optimization Advisor

![tests](https://github.com/sanjusanjay23/salary-optimization-advisor/actions/workflows/tests.yml/badge.svg)

A Flask web app that tells you where your salary stands in the market and what to do about it.
You enter your role, location and pay (and optionally upload a resume PDF). The app pulls
official U.S. Bureau of Labor Statistics wage percentiles, works out your market percentile,
and uses an open-weight LLM (gpt-oss-120b via Groq) to produce a personalized report: skill gaps with
estimated salary impact, a 4-step action plan, resume tips, alternative job titles and
negotiation advice.

Every number on the results page is labelled with where it came from (**BLS official data**,
**H1B filing data**, **Estimate**, or **AI suggestion**), so users can tell verified data apart
from model-generated advice.

## How it works

```
Form + resume PDF
      │
      ▼
Resume parser (PyPDF2, in memory) ──► skills / certifications / education / years of experience
      │
      ▼
Salary data:  BLS OEWS API  ──fail──►  H1B public filings  ──fail──►  labelled estimates
      │        (real p25 / median / p75 / p90, cached 24h)
      ▼
Percentile calculation (piecewise linear interpolation)
      │
      ▼
gpt-oss-120b (Groq) ── exact JSON schema in prompt, JSON mode, temperature 0.3, validation
      │
      ▼
Results page (Jinja2 + vanilla JS salary distribution chart)
```

| Layer | Technology |
|---|---|
| Web app | Flask, Jinja2, Gunicorn |
| Resume parsing | PyPDF2, regex keyword extraction (60+ terms) |
| Salary data | BLS OEWS public API, H1B salary disclosures (BeautifulSoup) |
| AI analysis | gpt-oss-120b (open-weight) via Groq API, model configurable |
| Frontend | HTML, CSS, vanilla JavaScript (no chart library) |
| Quality | pytest (36 tests, network and LLM mocked), GitHub Actions CI, Docker |

## Run locally

Requires Python 3.10+ and a free Groq API key from https://console.groq.com.

```bash
git clone https://github.com/sanjusanjay23/salary-optimization-advisor.git
cd salary-optimization-advisor
python -m venv venv
# Windows: venv\Scripts\activate     macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then put your GROQ_API_KEY in .env
python app.py
```

Open http://127.0.0.1:5000.

### With Docker

```bash
docker build -t salary-advisor .
docker run -p 5000:5000 --env-file .env salary-advisor
```

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | yes | LLM access |
| `FLASK_SECRET_KEY` | recommended | Signs the session cookie (random per start if unset) |
| `GROQ_MODEL` | optional | Override the LLM (default `openai/gpt-oss-120b`) |
| `BLS_API_KEY` | optional | Free [BLS registration key](https://data.bls.gov/registrationEngine/): 500 requests/day instead of 25 |
| `FLASK_DEBUG` | optional | `true` for local debugging only |

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

The tests cover the BLS series-ID format and response parsing, caching, rate-limit and fallback
behaviour, percentile maths, resume keyword matching, LLM JSON parsing, and the full
form → analysis → results flow, with all external calls mocked.

## Design notes

- **Legal data sources only.** An early version scraped Glassdoor and Indeed. That breaks their
  Terms of Service, so it was replaced with the official BLS API and public H1B disclosures.
- **Real percentiles.** The app requests the BLS 25th/50th/75th/90th percentile series directly
  (OEWS series IDs `OEUN0000000000000<SOC><type>`) and doesn't estimate them from the mean.
- **Reports stay on the server.** A full report is larger than the 4 KB browser cookie limit, so
  the cookie holds only a report ID; reports expire after an hour. Resumes are parsed in memory
  and never written to disk.
- **Known limitations.** BLS data is national and grouped by broad SOC code (a frontend engineer
  and an ML engineer share code 15-1252). AI-generated salary-boost figures are estimates and
  are labelled that way.

## Team

Built as the final project for an MS in Artificial Intelligence course at Northeastern University.

- **Sanjay**: frontend (input form, results page, salary distribution chart), H1B salary-data
  integration and data-transparency labels, LLM output schema and JSON parsing, tests, Docker
  and CI.
- **Chidvilash Yeccharla**: Flask backend architecture, BLS API integration, resume parser,
  Groq LLM integration.

The original version used LLaMA 3.3 70B; Groq retired that model, so the default is now
gpt-oss-120b, which also cut report generation from ~25 s to ~3 s.
