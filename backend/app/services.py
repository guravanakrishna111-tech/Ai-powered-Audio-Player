from app.db.connection import db
from app.processing.engine import ProcessingEngine
from app.scanner.library_scanner import LibraryScanner
from app.recommendation.recommender import RecommendationEngine

scanner = LibraryScanner(db)
engine = ProcessingEngine(db)
recommender = RecommendationEngine(db)
