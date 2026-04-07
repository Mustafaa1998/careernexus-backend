from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.resume import router as resume_router
from routers.jobs import router as jobs_router
from routers.universities import router as unis_router

app = FastAPI(title="CareerNexus Recommender")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
    allow_credentials=True
)

app.include_router(resume_router)
app.include_router(jobs_router)
app.include_router(unis_router)

@app.get("/health")
def health(): return {"ok": True}
