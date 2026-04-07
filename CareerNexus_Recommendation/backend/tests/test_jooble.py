import os, httpx
from dotenv import load_dotenv
load_dotenv("../.env")

key = os.getenv("JOOBLE_API_KEY")
url = f"https://jooble.org/api/{key}"

payload = {"keywords": "software developer", "location": "Pakistan"}
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

print("🔹 Testing Jooble (POST)...")
r = httpx.post(url, json=payload, headers=headers, timeout=30)
print("Status code:", r.status_code)
print("Raw text:", r.text[:300])
if r.status_code == 200:
    data = r.json()
    print("Total jobs:", len(data.get("jobs", [])))
