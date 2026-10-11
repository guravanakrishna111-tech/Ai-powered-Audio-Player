from fastapi import APIRouter, BackgroundTasks

from app.services import engine
from app.db.repository import LibraryRepository
from app.db.connection import db

router = APIRouter(tags=["processing"])
repo = LibraryRepository(db)


@router.get("/processing/progress")
def processing_progress() -> dict:
    return engine.get_progress()


@router.get("/processing/stats")
def processing_stats() -> dict:
    return repo.get_processing_stats()


@router.post("/processing/start")
def start_processing() -> dict:
    """Ensure the background processing engine is running."""
    engine.start()
    return {"ok": True, "is_running": engine.is_running}


@router.post("/processing/train")
def train_model(background_tasks: BackgroundTasks) -> dict:
    """Run model training and feature extraction."""
    background_tasks.add_task(engine.train_now)
    return {"ok": True, "message": "Model training started in background"}
