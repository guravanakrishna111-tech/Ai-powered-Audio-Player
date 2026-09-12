from fastapi import APIRouter, HTTPException, Query

from app.services import recommender

router = APIRouter(tags=["recommendations"])


@router.get("/recommendations/{song_id}")
def get_recommendations(
    song_id: int,
    limit: int = Query(5, ge=1, le=20),
) -> dict:
    try:
        return recommender.recommend(song_id, limit)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard for API stability
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {exc}") from exc

