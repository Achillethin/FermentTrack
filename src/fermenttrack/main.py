"""FermentTrack API entrypoint."""

from fastapi import FastAPI

from fermenttrack.routers import batches, cultures, ingredients, reminders, safety, webhooks

app = FastAPI(
    title="FermentTrack",
    description="Batch journal and smart reminders for serious fermenters",
    version="0.1.0",
)

app.include_router(cultures.router)
app.include_router(batches.router)
app.include_router(ingredients.router)
app.include_router(reminders.router)
app.include_router(safety.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
