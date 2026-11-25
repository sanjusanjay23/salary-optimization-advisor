"""
utils/llm_analyzer.py
---------------------
Generates the salary report with an open-weight LLM served by the Groq API
(default: openai/gpt-oss-120b; override with the GROQ_MODEL env variable).
The prompt embeds the exact JSON schema, JSON mode is enabled, and
temperature 0.3 keeps output consistent.
"""

import json
import re
import os
from groq import Groq

DEFAULT_MODEL = "openai/gpt-oss-120b"


def build_prompt(
    job_title, location, current_salary, years_exp,
    education, industry, skills_text, resume_text,
    resume_keywords, salary_data, percentile,
):
    market_median = salary_data.get("median", 90000)
    market_p25    = salary_data.get("p25", 65000)
    market_p75    = salary_data.get("p75", 115000)
    market_p90    = salary_data.get("p90", 145000)
    data_source   = salary_data.get("source", "Market estimates")

    found_skills = ", ".join(resume_keywords.get("skills", [])) or "not detected"
    found_certs  = ", ".join(resume_keywords.get("certifications", [])) or "none found"
    found_edu    = ", ".join(resume_keywords.get("education", [])) or "not specified"

    resume_section = (
        f"\n--- RESUME TEXT ---\n{resume_text[:3000]}\n--- END RESUME ---\n"
        if resume_text and len(resume_text) > 50
        else "\n[No resume provided — base analysis on profile details only]\n"
    )

    return f"""You are a senior compensation analyst and career coach.
Analyze the profile below and return ONLY a raw JSON object.
No markdown, no backticks, no explanation. Start with {{ and end with }}.

=== USER PROFILE ===
Job Title:           {job_title}
Location:            {location}
Current Salary:      ${current_salary:,}
Years of Experience: {years_exp or "not specified"}
Education:           {education}
Industry:            {industry or "Technology"}
Listed Skills:       {skills_text or "not provided"}

=== RESUME ANALYSIS (PyPDF2 extracted) ===
Skills detected:     {found_skills}
Certifications:      {found_certs}
Education keywords:  {found_edu}
{resume_section}

=== SALARY MARKET DATA ({data_source}) ===
25th percentile: ${market_p25:,}
Median:          ${market_median:,}
75th percentile: ${market_p75:,}
90th percentile: ${market_p90:,}
User percentile: {percentile}th

Return EXACTLY this JSON (all salary values as integers, no $ inside values, no nulls):

{{
  "summary_headline": "<one compelling sentence>",
  "market_context": "<2-3 sentences about market trends>",
  "percentile_analysis": "<1-2 sentences about their percentile>",
  "resume_strengths": ["<s1>", "<s2>", "<s3>", "<s4>"],
  "skill_gaps": [
    {{"skill":"<n>","impact":"high","salary_boost":"$8,000-$15,000","how_to_learn":"<course>"}},
    {{"skill":"<n>","impact":"medium","salary_boost":"$5,000-$10,000","how_to_learn":"<course>"}},
    {{"skill":"<n>","impact":"medium","salary_boost":"$3,000-$7,000","how_to_learn":"<course>"}},
    {{"skill":"<n>","impact":"low","salary_boost":"$2,000-$5,000","how_to_learn":"<course>"}}
  ],
  "resume_improvement_tips": ["<t1>","<t2>","<t3>","<t4>"],
  "certifications_to_pursue": [
    {{"name":"<c>","provider":"<p>","salary_impact":"$X-$Y","timeline":"<t>"}},
    {{"name":"<c>","provider":"<p>","salary_impact":"$X-$Y","timeline":"<t>"}},
    {{"name":"<c>","provider":"<p>","salary_impact":"$X-$Y","timeline":"<t>"}}
  ],
  "action_plan": [
    {{"step":1,"title":"<t>","description":"<d>","timeline":"1-2 months","salary_impact":"$X-$Y","priority":"high"}},
    {{"step":2,"title":"<t>","description":"<d>","timeline":"2-4 months","salary_impact":"$X-$Y","priority":"high"}},
    {{"step":3,"title":"<t>","description":"<d>","timeline":"3-6 months","salary_impact":"$X-$Y","priority":"medium"}},
    {{"step":4,"title":"<t>","description":"<d>","timeline":"6-12 months","salary_impact":"$X-$Y","priority":"medium"}}
  ],
  "potential_salary": <integer>,
  "alternative_titles": [
    {{"title":"<r>","salary_range":"$X-$Y","match_pct":<int>}},
    {{"title":"<r>","salary_range":"$X-$Y","match_pct":<int>}},
    {{"title":"<r>","salary_range":"$X-$Y","match_pct":<int>}},
    {{"title":"<r>","salary_range":"$X-$Y","match_pct":<int>}}
  ],
  "negotiation_tips": ["<t1>","<t2>","<t3>","<t4>"],
  "top_companies": ["<c1>","<c2>","<c3>","<c4>","<c5>","<c6>"]
}}"""


def parse_llm_json(raw_text: str) -> dict:
    """
    Extract the outermost JSON object from an LLM response, tolerating
    markdown code fences or stray text around it.
    """
    cleaned = re.sub(r"```(?:json)?", "", raw_text).strip()
    json_match = re.search(r"\{[\s\S]*\}", cleaned)
    if not json_match:
        raise ValueError(f"No valid JSON in response. Raw: {raw_text[:300]}")

    try:
        report = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse error: {e}")

    if not isinstance(report, dict):
        raise ValueError("LLM response JSON is not an object.")
    return report


def analyze_with_llm(
    job_title, location, current_salary, years_exp,
    education, industry, skills_text, resume_text,
    resume_keywords, salary_data, percentile,
):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or "your" in api_key.lower():
        raise ValueError("GROQ_API_KEY is not set in your .env file.")

    client = Groq(api_key=api_key)

    prompt = build_prompt(
        job_title=job_title, location=location,
        current_salary=current_salary, years_exp=years_exp,
        education=education, industry=industry,
        skills_text=skills_text, resume_text=resume_text,
        resume_keywords=resume_keywords, salary_data=salary_data,
        percentile=percentile,
    )

    print("[LLM] Sending request to Groq API...")

    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL") or DEFAULT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a senior compensation analyst. Return ONLY raw JSON — no markdown, no backticks. Start with { and end with }.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=8192,
        response_format={"type": "json_object"},
        # gpt-oss is a reasoning model; low effort keeps responses fast
        extra_body={"reasoning_effort": "low"},
    )

    raw_text = (response.choices[0].message.content or "").strip()
    print(f"[LLM] Response received ({len(raw_text)} chars)")

    report = parse_llm_json(raw_text)

    report["salary_data"] = salary_data
    report["percentile"]  = percentile

    print("[LLM] Analysis complete.")
    return report