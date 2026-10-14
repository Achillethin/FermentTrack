"""FermentTrack API entrypoint."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fermenttrack import database
from fermenttrack.config import settings
from fermenttrack.recommender import calibration, community, jobs
from fermenttrack.routers import (
    admin,
    batches,
    cultures,
    foods,
    ingredients,
    me,
    organisms,
    prediction,
    recipes,
    recommendations,
    reminders,
    safety,
    sourdough,
    tastings,
    webhooks,
)
from fermenttrack.routers import community as community_routes


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """The recommender's background job worker (design § 10.2) runs as long as the app. At
    startup, approved community recipes whose forecasts are missing or of another grid are
    queued again (design § 10.3; importing recommender.community registers their job kind),
    and the calibration gate (design § 13.2) loads its latest report, recomputed when missing
    or a week old, then again weekly (recommender.calibration.run_schedule)."""
    worker = jobs.Worker(database.async_session_maker)
    await worker.start()
    tasks = [
        asyncio.create_task(
            community.recompute_at_startup(database.async_session_maker),
            name="community-forecasts-recompute",
        ),
        asyncio.create_task(
            calibration.run_schedule(database.async_session_maker), name="calibration-schedule"
        ),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await worker.stop()


app = FastAPI(
    title="FermentTrack",
    description="Batch journal and smart reminders for serious fermenters",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cultures.router)
app.include_router(me.router)
app.include_router(batches.router)
app.include_router(ingredients.router)
app.include_router(foods.router)
app.include_router(organisms.router)
app.include_router(reminders.router)
app.include_router(safety.router)
app.include_router(prediction.router)
app.include_router(sourdough.router)
app.include_router(webhooks.router)
app.include_router(admin.router)
app.include_router(recipes.router)
app.include_router(recommendations.router)
app.include_router(community_routes.router)
app.include_router(tastings.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
