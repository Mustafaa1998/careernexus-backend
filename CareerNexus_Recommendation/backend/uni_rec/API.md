# CareerNexus – University Recommender API

**Base URL:** `http://127.0.0.1:8001`

All endpoints return JSON. CORS is enabled for local testing.

---

## 1) Suggest Programs (Discovery)
Groups universities by program for a given **field/level/city** with pagination.

### Endpoint
`GET /v1/suggest/programs`

### Query Params
- `field` *(string, optional)* — e.g. `computer science`, `cs`, `it`
- `city` *(string, optional)* — e.g. `karachi`
- `level` *(string, optional)* — `bs` | `ms` | `phd`
- `page` *(int, default=1)*
- `page_size` *(int, default=20)* — number of program groups per page
- `universities_limit` *(int, default=8)* — max universities listed per program group

### Success Response (200)
```json
{
  "intent": "program_suggestions",
  "filters": { "field": "computer science", "city": "karachi", "level": "bs" },
  "page": 1,
  "next_page": 2,
  "total": 10,
  "programs": [
    {
      "program": "bs computer science",
      "display_name": "BS Computer Science",
      "universities_count": 13,
      "universities": [
        {
          "university_name": "NED University of Engineering & Technology",
          "city": "Karachi",
          "province": "Sindh",
          "ranking": "A",
          "website_url": "https://www.neduet.edu.pk",
          "apply_url": "https://www.neduet.edu.pk/admissions"
        }
      ]
    }
  ]
}
