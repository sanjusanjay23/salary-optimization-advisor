"""
utils/salary_scraper.py
-----------------------
Fetches salary market data from legally compliant, structured sources:

  1. Bureau of Labor Statistics (BLS) OEWS API  (primary)
     Official US Government wage percentiles (p25 / median / p75 / p90).
     Free; optional BLS_API_KEY raises the daily request limit.
     https://www.bls.gov/oes/

  2. H1B public salary filings (h1bdata.info)  (secondary)
     Employers are legally required to disclose H1B salaries, so this is
     public record data of real offered wages.

  3. Hard-coded role-category estimates  (final fallback)
     Used only when both live sources fail, and labelled as estimates.

Glassdoor / Indeed scraping was intentionally removed because it violates
those sites' Terms of Service.
"""

import os
import time

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ── BLS SOC Code Mapping ───────────────────────────────────────────────────
BLS_SOC_MAP = {
    "software engineer":      "15-1252",
    "software developer":     "15-1252",
    "data scientist":         "15-2051",
    "data analyst":           "15-2041",
    "machine learning":       "15-2051",
    "ai engineer":            "15-1299",
    "devops":                 "15-1244",
    "cloud engineer":         "15-1244",
    "product manager":        "11-2021",
    "project manager":        "11-3021",
    "business analyst":       "13-1111",
    "frontend developer":     "15-1252",
    "backend developer":      "15-1252",
    "full stack":             "15-1252",
    "systems analyst":        "15-1211",
    "database administrator": "15-1242",
    "cybersecurity":          "15-1212",
    "network engineer":       "15-1241",
    "ux designer":            "27-1021",
    "financial analyst":      "13-2051",
    "accountant":             "13-2011",
    "marketing manager":      "11-2021",
    "nurse":                  "29-1141",
    "physician":              "29-1215",
    "teacher":                "25-2031",
    "lawyer":                 "23-1011",
    "civil engineer":         "17-2051",
    "mechanical engineer":    "17-2141",
    "electrical engineer":    "17-2071",
}

# ── Hardcoded Fallback Data ────────────────────────────────────────────────
FALLBACK_DATA = {
    "software_engineer": {
        "p25": 95000, "median": 130000, "p75": 165000, "p90": 200000,
        "source": "Estimated market data (2024-2025)",
        "source_type": "estimate"
    },
    "data_scientist": {
        "p25": 90000, "median": 120000, "p75": 155000, "p90": 185000,
        "source": "Estimated market data (2024-2025)",
        "source_type": "estimate"
    },
    "product_manager": {
        "p25": 100000, "median": 135000, "p75": 175000, "p90": 215000,
        "source": "Estimated market data (2024-2025)",
        "source_type": "estimate"
    },
    "default": {
        "p25": 65000, "median": 90000, "p75": 115000, "p90": 145000,
        "source": "Estimated market data (2024-2025)",
        "source_type": "estimate"
    },
}


def _match_bls_code(job_title: str) -> str | None:
    """Find the closest BLS SOC code for a given job title."""
    title_lower = job_title.lower()
    for keyword, code in BLS_SOC_MAP.items():
        if keyword in title_lower:
            return code
    return None


# ── SOURCE 1: BLS OEWS API (Primary) ──────────────────────────────────────
BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# OEWS data-type codes for annual wage percentiles
BLS_DATATYPES = {"p25": "12", "median": "13", "p75": "14", "p90": "15"}

# The keyless BLS API allows 25 requests/day, so results are cached per SOC
# code. Set BLS_API_KEY (free registration) to raise the limit to 500/day.
_CACHE_TTL_SECONDS = 24 * 60 * 60
_bls_cache: dict[str, tuple[float, dict]] = {}


def _bls_series_id(soc_code: str, datatype: str) -> str:
    """
    Build a national OEWS series ID (25 characters):
      OEU + N (national) + 0000000 (area) + 000000 (all industries)
      + 6-digit SOC code + 2-digit data type
    """
    return f"OEUN0000000000000{soc_code.replace('-', '')}{datatype}"


def _fetch_bls_salary(job_title: str) -> dict | None:
    """
    Query the Bureau of Labor Statistics OEWS API for the real
    national 25th / 50th / 75th / 90th wage percentiles.
    Free, no API key, official US Government data.
    """
    soc_code = _match_bls_code(job_title)
    if not soc_code:
        return None

    cached = _bls_cache.get(soc_code)
    if cached and time.time() - cached[0] < _CACHE_TTL_SECONDS:
        return dict(cached[1])

    series = {key: _bls_series_id(soc_code, dt) for key, dt in BLS_DATATYPES.items()}
    payload = {"seriesid": list(series.values()), "latest": True}
    api_key = os.getenv("BLS_API_KEY")
    if api_key:
        payload["registrationkey"] = api_key

    try:
        resp = requests.post(BLS_API_URL, json=payload, timeout=10)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if data.get("status") != "REQUEST_SUCCEEDED":
            return None

        values, year = {}, None
        for item in data.get("Results", {}).get("series", []):
            points = item.get("data") or []
            if not points:
                continue
            try:
                # BLS reports top-coded wages as "-" or "*"; skip those
                values[item["seriesID"]] = float(points[0]["value"])
                year = points[0].get("year", year)
            except (KeyError, ValueError):
                continue

        result = {key: values.get(sid) for key, sid in series.items()}
        if not result["p25"] or not result["median"] or result["median"] < 20000:
            return None
        if not result["p75"]:
            result["p75"] = result["median"] * 1.25
        if not result["p90"]:
            # p90 is top-coded for very high-paying roles
            result["p90"] = result["p75"] * 1.2

        label = f"BLS OEWS Official Data {year}" if year else "BLS OEWS Official Data"
        salary = {
            "p25":         round(result["p25"]),
            "median":      round(result["median"]),
            "p75":         round(result["p75"]),
            "p90":         round(result["p90"]),
            "source":      f"{label} (SOC {soc_code})",
            "source_type": "government_api",
        }
        _bls_cache[soc_code] = (time.time(), salary)
        return dict(salary)

    except Exception as e:
        print(f"[SalaryScraper] BLS API error: {e}")
        return None


# ── SOURCE 2: H1B Salary Data (Secondary) ─────────────────────────────────
def _fetch_h1b_salary(job_title: str, location: str) -> dict | None:
    """
    Fetch salary data from H1B public visa filing disclosures.

    H1B regulations require employers to publicly disclose
    salaries offered to foreign workers. This data is:
    - Legally public and compliant to use
    - Contains real reported salaries not user estimates
    - Source: https://h1bdata.info/

    Replaces BeautifulSoup scraping of Glassdoor/Indeed
    which violates their Terms of Service.
    """
    try:
        job_query  = job_title.lower().replace(" ", "+")
        city_query = location.split(",")[0].strip().lower().replace(" ", "+")

        url = (
            f"https://h1bdata.info/index.php?"
            f"em=&job={job_query}&city={city_query}&year=2024"
        )

        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        table = soup.find("table", {"id": "myTable"})
        if not table:
            table = soup.find("table")
        if not table:
            return None

        salaries = []
        rows = table.find_all("tr")[1:]

        for row in rows[:50]:
            cells = row.find_all("td")
            if len(cells) >= 4:
                for cell in cells[2:5]:
                    text = cell.get_text(strip=True).replace(",", "").replace("$", "")
                    try:
                        val = int(float(text))
                        if 25000 < val < 800000:
                            salaries.append(val)
                            break
                    except ValueError:
                        continue

        if len(salaries) < 5:
            return None

        salaries.sort()
        n = len(salaries)

        return {
            "p25":         salaries[int(n * 0.25)],
            "median":      salaries[int(n * 0.50)],
            "p75":         salaries[int(n * 0.75)],
            "p90":         salaries[int(n * 0.90)],
            "source":      f"H1B Public Salary Filings — {n} records",
            "source_type": "h1b_filings",
        }

    except Exception as e:
        print(f"[SalaryScraper] H1B data error: {e}")
        return None


# ── SOURCE 3: Hardcoded Fallback ───────────────────────────────────────────
def _get_fallback(job_title: str) -> dict:
    """Final fallback — used only if all live sources fail."""
    title_lower = job_title.lower()

    if any(k in title_lower for k in
           ["software", "developer", "engineer", "devops", "cloud"]):
        return FALLBACK_DATA["software_engineer"]

    if any(k in title_lower for k in
           ["data scientist", "ml", "machine learning", "ai"]):
        return FALLBACK_DATA["data_scientist"]

    if any(k in title_lower for k in ["product manager", "pm"]):
        return FALLBACK_DATA["product_manager"]

    return FALLBACK_DATA["default"]


# ── Master Function ────────────────────────────────────────────────────────
def get_salary_data(job_title: str, location: str) -> dict:
    """
    Master salary data function.
    Priority: BLS API → H1B Data → Hardcoded Fallback
    Always returns a valid dict — app never crashes.
    """
    print(f"[SalaryScraper] Fetching: {job_title} in {location}")

    result = _fetch_bls_salary(job_title)
    if result:
        print(f"[SalaryScraper] BLS data: median=${result['median']:,}")
        return result

    time.sleep(0.5)

    result = _fetch_h1b_salary(job_title, location)
    if result:
        print(f"[SalaryScraper] H1B data: median=${result['median']:,}")
        return result

    print(f"[SalaryScraper] Using fallback estimates")
    return dict(_get_fallback(job_title))


# ── Percentile Calculator ──────────────────────────────────────────────────
def calculate_percentile(current_salary: int, salary_data: dict) -> int:
    """
    Estimates salary percentile using piecewise linear interpolation.
    """
    p25    = salary_data.get("p25",    60000)
    median = salary_data.get("median", 90000)
    p75    = salary_data.get("p75",   120000)
    p90    = salary_data.get("p90",   150000)

    if current_salary <= p25:
        ratio = max(0, current_salary / p25)
        return max(5, round(ratio * 25))
    elif current_salary <= median:
        ratio = (current_salary - p25) / max(1, median - p25)
        return round(25 + ratio * 25)
    elif current_salary <= p75:
        ratio = (current_salary - median) / max(1, p75 - median)
        return round(50 + ratio * 25)
    elif current_salary <= p90:
        ratio = (current_salary - p75) / max(1, p90 - p75)
        return round(75 + ratio * 15)
    else:
        return min(99, round(90 + (current_salary - p90) / p90 * 10))