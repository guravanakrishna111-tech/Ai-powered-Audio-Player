"""Diversity re-ranking for recommendation results.

Goal
----
Given a ranked list of candidates (highest score first), return a re-ranked
list where no single artist dominates the top-N results.

Algorithm
---------
We use a simplified Maximal Marginal Relevance (MMR) style pass:

    1. Walk the sorted candidates in score order.
    2. Track how many times each artist already appears in the *selected* set.
    3. If an artist appears >= ``max_per_artist`` times, multiply the
       candidate's score by (1 - penalty) before inserting it into the
       output list. The candidate is still included — just demoted.
    4. Re-sort the output by the (possibly penalised) score so the relative
       ordering within non-penalised candidates is preserved.

Why this approach
-----------------
* O(N) pass — negligible latency even for large libraries.
* Interpretable: every output score is either the original score or
  ``original × (1 - penalty)``. No black-box re-embedding.
* Conservative: we do not remove candidates, only demote. If the library
  genuinely consists of only one artist the user still gets recommendations.
* Configurable via ``max_per_artist`` and ``penalty``.

Limitations
-----------
* Artist identity is determined by ``artist_id``. Songs with ``artist_id=None``
  are all treated as "unknown artist" and do not accumulate counts against
  each other (they use a sentinel key so they are never penalised).
* The penalty is flat, not progressive. A third occurrence receives the same
  discount as a tenth occurrence. Progressive penalties could be added later.
"""
from __future__ import annotations

from app.recommendation.models import RecommendationItem

_NO_ARTIST_SENTINEL = object()


def apply_diversity(
    items: list[RecommendationItem],
    max_per_artist: int = 2,
    penalty: float = 0.15,
) -> list[RecommendationItem]:
    """Re-rank *items* to reduce same-artist repetition.

    Parameters
    ----------
    items:
        Candidates already sorted by score descending.  This list is not
        mutated; a new list is returned.
    max_per_artist:
        How many times an artist may appear in the selected set before the
        penalty kicks in for subsequent appearances.
    penalty:
        Fractional score reduction applied when the artist cap is exceeded.
        ``0.15`` means the score is multiplied by ``0.85``.

    Returns
    -------
    list[RecommendationItem]
        Re-ranked list, sorted by effective score descending.
        Each item's ``.score`` field is updated to the effective score so
        that the UI and audit trail reflect the post-diversity value.
    """
    if max_per_artist <= 0 or penalty <= 0.0 or not items:
        return list(items)

    artist_counts: dict[object, int] = {}
    result: list[RecommendationItem] = []

    for item in items:
        # Use artist_id as key; None → sentinel so unknown artists don't
        # accumulate counts against each other.
        artist_key = item.song.artist_id if item.song.artist_id is not None else id(item)
        count = artist_counts.get(artist_key, 0)

        effective_score = item.score
        if count >= max_per_artist:
            effective_score = item.score * (1.0 - penalty)
            # Record the diversity adjustment in the breakdown details so the
            # audit trail is honest about what happened.
            item.breakdown.details["diversity_penalty"] = round(penalty, 4)

        artist_counts[artist_key] = count + 1

        # Mutate score on the item itself so that the final sort and the API
        # response both reflect the post-diversity score.
        item.score = round(effective_score, 4)
        result.append(item)

    # Re-sort by effective score; preserve original tiebreaker.
    result.sort(key=lambda i: (-i.score, i.song.artist_name or "", i.song.title or ""))
    return result
