"""
hec_scraper.py — Wikipedia FEST + detail crawler (robust)
- Scrapes the main list page (tables + lists)
- Visits each university page, extracts website + program keywords
- Merges with local datasets when present
"""

from __future__ import annotations
import re
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

LIST_URL = "https://en.wikipedia.org/wiki/List_of_engineering_universities_and_colleges_in_Pakistan"
OUTPUT_MAIN   = DATA_DIR / "wiki_fest_links.csv"
OUTPUT_DETAIL = DATA_DIR / "wiki_universities_detailed.csv"
HEC_FILE      = DATA_DIR / "hec_universities.csv"           # optional
FEST_FILE     = DATA_DIR / "pakistan_fest_programs.csv"     # optional
OUTPUT_FINAL  = DATA_DIR / "hec_fest_universities.csv"

# ------------------------------------------------------------
# HTTP helpers
# ------------------------------------------------------------
SESSION = requests.Session()
SESSION.headers.update({
    # A friendly UA avoids blocks and returns full HTML
    "User-Agent": "CareerNexus-FEST-Scraper/1.0 (+https://example.com) Python-requests",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "close",
})

def get_soup(url: str) -> BeautifulSoup:
    resp = SESSION.get(url, timeout=25)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")

def norm_name(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def link_is_article(href: str) -> bool:
    if not href or not href.startswith("/wiki/"):
        return False
    # filter out non-articles
    bad = (":", "List_of")
    return not any(b in href for b in bad)

# ------------------------------------------------------------
# Step 1 – Scrape the list page (tables + lists)
# ------------------------------------------------------------
print("🔍 Fetching main list of engineering universities...")
soup = get_soup(LIST_URL)

records: list[dict] = []

# A) tables.wikitable
for tbl in soup.select("table.wikitable"):
    for a in tbl.select("a[href^='/wiki/']"):
        if not link_is_article(a.get("href", "")):
            continue
        name = norm_name(a.get_text())
        if not name:
            continue
        url = "https://en.wikipedia.org" + a["href"]
        records.append({"university_name": name, "wiki_url": url})

# B) lists (many sections use bullet lists)
content = soup.select_one("div.mw-parser-output")
if content:
    for li in content.select("ul li"):
        a = li.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        if not link_is_article(href):
            continue
        name = norm_name(a.get_text())
        if not name:
            continue
        url = "https://en.wikipedia.org" + href
        records.append({"university_name": name, "wiki_url": url})

df_links = pd.DataFrame(records).drop_duplicates(subset=["wiki_url"]).reset_index(drop=True)

# Heuristic: keep obvious university domains/titles (reduce noise)
df_links = df_links[~df_links["university_name"].str.contains(r"^\d+$", na=False)]
df_links.to_csv(OUTPUT_MAIN, index=False)

print(f"✅ Found {len(df_links)} universities in the list.")

if df_links.empty:
    print("⚠️ No universities were parsed from the list page. "
          "Wikipedia layout may have changed or the request was blocked.\n"
          "Try again in a bit, or check your network/UA.")
    # still produce empty outputs gracefully
    pd.DataFrame(columns=["university_name","wiki_url","website_url",
                          "programs_detected","offers_FEST"]).to_csv(OUTPUT_DETAIL, index=False)
    pd.DataFrame(columns=["university_name"]).to_csv(OUTPUT_FINAL, index=False)
    raise SystemExit(0)

# ------------------------------------------------------------
# Step 2 – Visit each university page and extract info
# ------------------------------------------------------------
details: list[dict] = []
for _, row in tqdm(df_links.iterrows(), total=len(df_links), desc="Scraping detail pages"):
    name = row["university_name"]
    link = row["wiki_url"]
    try:
        soup_u = get_soup(link)
        text = soup_u.get_text(" ").lower()

        # program phrases like "bs xxx", "be yyy", "ms zzz", "phd abc"
        progs = re.findall(r"\b(?:bs|be|bsc|ms|msc|m\.?phil|mphil|phd)\s+[a-z&/\- ]{2,40}", text)
        progs = [norm_name(p) for p in progs if 3 <= len(p) <= 50]

        # find a plausible official website (prefer *.edu.pk)
        website = ""
        for a in soup_u.select("a[href^='http']"):
            href = a.get("href") or ""
            if any(x in href for x in (".edu.pk", ".edu", "university")):
                website = href
                break

        offers_fest = any(k in text for k in [
            "engineering", "technology", "computer science",
            "information technology", "applied science", "software engineering"
        ])

        details.append({
            "university_name": name,
            "wiki_url": link,
            "website_url": website,
            "programs_detected": ", ".join(sorted(set(progs))),
            "offers_FEST": bool(offers_fest),
        })
    except Exception as e:
        # Keep going even if a page fails
        details.append({
            "university_name": name,
            "wiki_url": link,
            "website_url": "",
            "programs_detected": "",
            "offers_FEST": "",
            "error": str(e),
        })

df_detail = pd.DataFrame(details)
df_detail.to_csv(OUTPUT_DETAIL, index=False)
print(f"✅ Saved {len(df_detail)} detailed rows → {OUTPUT_DETAIL}")

# ------------------------------------------------------------
# Step 3 – Optional merges (don’t crash if files are missing)
# ------------------------------------------------------------
print("🔗 Merging with HEC + local FEST datasets (if present)...")

def _key(n: str) -> str:
    s = (n or "").lower()
    s = s.replace("&", "and")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

df_detail["univ_key"] = df_detail["university_name"].apply(_key)

merged = df_detail.copy()

if HEC_FILE.exists():
    df_hec = pd.read_csv(HEC_FILE).fillna("")
    df_hec["univ_key"] = df_hec["university_name"].apply(_key)
    merged = merged.merge(df_hec, on="univ_key", how="left", suffixes=("", "_hec"))
else:
    print(f"⚠️ Skipping merge: {HEC_FILE} not found.")

if FEST_FILE.exists():
    df_fest = pd.read_csv(FEST_FILE).fillna("")
    df_fest["univ_key"] = df_fest["university_name"].apply(_key)
    merged = merged.merge(df_fest, on="univ_key", how="left", suffixes=("", "_fest"))
else:
    print(f"⚠️ Skipping merge: {FEST_FILE} not found.")

merged["verified_by_HEC"] = merged.get("university_name_hec").notna() if "university_name_hec" in merged.columns else False
if "ranking_tier" not in merged.columns:
    merged["ranking_tier"] = "B"

merged.to_csv(OUTPUT_FINAL, index=False)
print(f"🎓 Final dataset saved → {OUTPUT_FINAL} ({len(merged)} rows)")
