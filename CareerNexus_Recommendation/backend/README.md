What this folder does
→ “This is the Job Recommendation Backend.”

What it connects to
→ “It connects to APIs like JSearch, SerpAPI, etc.”

How to set it up

Go to this folder

Activate the environment

Install requirements

Copy .env.example → rename to .env

Fill in your keys

How to run it

Option A: Run the command

uvicorn app_fest:app --reload --port 8000


Option B: Just double-click run_job.bat.

What URLs/endpoints exist
Example:

/v1/jobs/search → find jobs

/recommend/jobs_live → recommend jobs

/debug/serpapi → test your connection

/unirec/... → connect to uni_rec (if you want)

Where the other backend is
It reminds you:

Job backend is on port 8000

University backend is on port 8001

That you have frozen it
Meaning your setup is done and stable.

What to do next
Later you’ll connect:

Resume parser (to extract skills)

Psychometric test results

Chatbot (to show everything together)