import os, httpx
from dotenv import load_dotenv
load_dotenv("../.env")

key = os.getenv("SERPAPI_KEY")
url = "https://serpapi.com/search.json"
params = {
    "engine": "google_jobs",
    "q": "software developer in Pakistan",
    "api_key": key,
    "hl": "en"
}

print("🔹 Testing SerpAPI...")
r = httpx.get(url, params=params)
print("Status:", r.status_code)
jobs = r.json().get("jobs_results", [])
print("Jobs:", len(jobs))
print("First:", jobs[0] if jobs else "None")
