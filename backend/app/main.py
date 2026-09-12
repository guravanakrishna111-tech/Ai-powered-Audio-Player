from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import library, processing, recommendations, settings as settings_routes
from app.services import engine

app = FastAPI(title="AI Audio Player API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(library.router, prefix="/api")
app.include_router(processing.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")
app.include_router(settings_routes.router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    engine.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    engine.stop()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "ai-audio-player"}
