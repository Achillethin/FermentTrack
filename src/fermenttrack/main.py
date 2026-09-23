"""FermentTrack API entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fermenttrack.config import settings
from fermenttrack.routers import batches, cultures, foods, ingredients, reminders, safety, webhooks

app = FastAPI(
    title="FermentTrack",
    description="Batch journal and smart reminders for serious fermenters",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cultures.router)
app.include_router(batches.router)
app.include_router(ingredients.router)
app.include_router(foods.router)
app.include_router(reminders.router)
app.include_router(safety.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
