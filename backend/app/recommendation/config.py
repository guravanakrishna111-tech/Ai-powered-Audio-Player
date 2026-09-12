from dataclasses import dataclass


# ── Version identifiers stored in recommendation_history ────────────────────
ALGORITHM_VERSION = "part2b-v1"
CONFIG_VERSION = "weights-v2"
NORMALIZATION_STATE_KEY = "recommendation_normalization_v1"

# ── Diversity re-ranking ─────────────────────────────────────────────────────
# Maximum number of times a single artist may appear in the *selected* result
# set before a penalty is applied to subsequent candidates from that artist.
DIVERSITY_MAX_PER_ARTIST: int = 2

# Fractional score reduction applied when the per-artist cap is exceeded.
# 0.15 → effective_score = original_score × 0.85
DIVERSITY_ARTIST_PENALTY: float = 0.15


@dataclass(slots=True, frozen=True)
class RecommendationWeights:
    """Baseline weights for the multi-signal content-based recommender.

    These are engineering starting values — they are NOT claimed to be optimal.
    All weights in a single object so experiments can be run by substituting
    a different instance rather than patching scattered constants.

    Weights do NOT need to sum to 1.0 because the scoring code uses a
    denominator equal to the sum of *available* (non-None) component weights,
    so missing features are handled gracefully without re-normalising here.
    """
    audio: float = 0.40
    mood: float = 0.25
    genre: float = 0.15
    artist: float = 0.08
    language: float = 0.05
    album: float = 0.04
    other: float = 0.03


DEFAULT_WEIGHTS = RecommendationWeights()
