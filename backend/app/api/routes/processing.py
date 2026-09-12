from fastapi import APIRouter

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
