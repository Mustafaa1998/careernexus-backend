# schemas.py
from typing import Optional, Literal
from pydantic import BaseModel

class RecommendRequest(BaseModel):
    level: str = ""                 # bs | ms | phd
    field: str = ""                 # e.g., "computer science"
    city: str = ""                  # preferred city
    program_name: str = ""          # e.g., "software engineering"
    max_fee: Optional[int] = None
    limit: int = 30                 # still supported, but page_size preferred

    # 🔹 Polish filters
    province: str = ""              # e.g., "sindh"
    type: str = ""                  # "public" | "private"
    ranking_tier: str = ""          # "A" | "B" | "C"
    ranking_min: Optional[int] = None  # optional numeric policy if you add later
    offers_fest: Optional[bool] = None # True → only Eng/Science/Tech-ish

    # 🔹 Sorting + pagination
    sort_by: Literal['fee', 'ranking', 'name'] = 'ranking'
    order: Literal['asc', 'desc'] = 'asc'
    page: int = 1
    page_size: int = 30


class RecommendResponseItem(BaseModel):
    university_name: str = ""
    city: str = ""
    province: str = ""
    type: str = ""
    program_name: str = ""  # optional placeholder (not needed for MVP)
    level: str = ""
    field: str = ""
    ranking: str = ""
    website_url: str = ""
    apply_url: str = ""
