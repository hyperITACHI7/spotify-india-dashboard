from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import discovery

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Reset any stale "running" scrape state left over from a crashed process
    discovery._scrape_progress.update(discovery._fresh_progress())
    yield

app = FastAPI(
    title="Spotify Review Analysis API",
    description="Backend API serving NLP-enriched review data for the Indian market.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow React dashboard (typically running on localhost:3000 or 5173) to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to the exact dashboard domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(discovery.router)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Spotify Review Analysis API is running."}
