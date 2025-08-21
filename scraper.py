# scraper.py
import os
import re
import time
import urllib.parse
from datetime import datetime, timezone
from typing import List, Dict, Tuple

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from serpapi import GoogleSearch

# ----------------------------
# Env & DB setup
# ----------------------------
load_dotenv()  # read .env in project root

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "jobtracker")
COLL_NAME = os.getenv("COLL_NAME", "jobs")

SERPAPI_KEY = os.getenv("SERPAPI_KEY")  # required
KEYWORDS = os.getenv(
    "KEYWORDS",
    "devops,sre,site reliability,platform engineer,cloud engineer,kubernetes,terraform,ci/cd",
)
# You can provide multiple locations via LOCATIONS or a single LOCATION
LOCATIONS = os.getenv("LOCATIONS") or os.getenv("LOCATION", "United States")
LOCATIONS = [x.strip() for x in LOCATIONS.split(",") if x.strip()]

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col = db[COLL_NAME]
# De-dupe by link
col.create_index([("link", ASCENDING)], unique=True)

ALLOWED_DOMAINS = {"linkedin.com", "indeed.com", "glassdoor.com"}

# ----------------------------
# Helpers
# ----------------------------

def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def looks_like_legit_company(name: str) -> bool:
    if not name:
        return False
    n = name.lower()
    # quick heuristic to drop obvious junk
    bad = ["confidential", "hiring multiple", "urgent", "apply now",
           "recruiter", "staffing", "agency", "job opening"]
    if any(b in n for b in bad):
        return False
    if n in {"linkedin", "indeed", "glassdoor", "unknown"}:
        return False
    return 2 <= len(name) <= 80

def source_ok_and_name(link: str, via: str | None) -> Tuple[bool, str]:
    """
    Accept if 'via' explicitly says LinkedIn/Indeed/Glassdoor OR
    the link's domain belongs to one of those.
    """
    via_norm = (via or "").strip().lower()
    if via_norm in {"linkedin", "indeed", "glassdoor"}:
        return True, via_norm.capitalize()
    try:
        host = urllib.parse.urlparse(link).netloc.lower()
    except Exception:
        host = ""
    for dom in ALLOWED_DOMAINS:
        if host.endswith(dom):
            return True, dom.split(".")[0].capitalize()
    return False, via or "Unknown"

def upsert_job(doc: Dict):
    """Insert or update by job link."""
    now = datetime.now(timezone.utc).date().isoformat()
    doc.setdefault("first_seen", now)
    doc["last_seen"] = now
    doc.setdefault("applied", False)

    col.update_one(
        {"link": doc["link"]},
        {
            "$setOnInsert": {
                "title": doc.get("title"),
                "company": doc.get("company"),
                "location": doc.get("location"),
                "description": (doc.get("description") or "")[:1500],
                "source": doc.get("source"),
                "first_seen": doc["first_seen"],
                "applied": doc["applied"],
            },
            "$set": {
                "last_seen": doc["last_seen"],
            },
        },
        upsert=True,
    )

# ----------------------------
# SerpAPI fetch
# ----------------------------

def fetch_google_jobs(query: str, location: str) -> List[Dict]:
    if not SERPAPI_KEY:
        raise RuntimeError("SERPAPI_KEY is required. Put it in .env as SERPAPI_KEY=...")

    params = {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "hl": "en",
        "api_key": SERPAPI_KEY,
        "num": "100",
    }

    results = GoogleSearch(params).get_dict()
    jobs_out: List[Dict] = []

    for j in results.get("jobs_results", []) or []:
        title = normalize(j.get("title"))
        company = normalize(j.get("company_name"))
        via = normalize(j.get("via"))
        link = (
            (j.get("apply_options") or [{}])[0].get("link")
            or j.get("job_link")
            or j.get("link")
        )
        loc_txt = normalize(j.get("location"))
        desc = normalize(j.get("description"))

        if not title or not link:
            continue
        if not looks_like_legit_company(company):
            continue

        ok, src_name = source_ok_and_name(link, via)
        if not ok:
            continue

        jobs_out.append(
            {
                "title": title,
                "company": company,
                "location": loc_txt or location or "—",
                "description": desc,
                "link": link,
                "source": src_name,
            }
        )
    return jobs_out

# ----------------------------
# Orchestrator
# ----------------------------

def run():
    total_processed = 0
    for loc in LOCATIONS:
        for kw in [k.strip() for k in KEYWORDS.split(",") if k.strip()]:
            try:
                jobs = fetch_google_jobs(kw, loc)
            except Exception as e:
                print(f"[ERROR] fetch failed for '{kw}' in '{loc}': {e}")
                time.sleep(1)
                continue

            count = 0
            for job in jobs:
                try:
                    upsert_job(job)
                    count += 1
                except Exception as e:
                    # ignore individual failures but continue
                    print(f"[WARN] upsert failed for {job.get('link')}: {e}")

            total_processed += count
            print(
                f"[{datetime.now(timezone.utc).isoformat()}] "
                f"kw='{kw}' loc='{loc}' processed={len(jobs)} upserted_or_matched={count}"
            )

    print(
        f"[{datetime.now(timezone.utc).isoformat()}] TOTAL upserted_or_matched={total_processed}"
    )

if __name__ == "__main__":
    run()
