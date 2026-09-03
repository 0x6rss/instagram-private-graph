"""Finalize the backward-compatible numeric model-confidence score.

The 0..100 value comes from heuristic visibility assumptions. It is not a
calibrated probability, false-positive guarantee, or proof of a follow edge.
Legacy field and tier names remain for API compatibility.
"""

from .person import PersonRegistry


def finalize_scores(registry: PersonRegistry):
    """Copy heuristic confidence into the backward-compatible score field."""
    for p in registry:
        try:
            confidence = float(p.probability_1hop or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        p.score = round(max(0.0, min(100.0, confidence)), 2)
                                                                               
                                                                              
        p.score_valid = p.hop_class != 'unknown'

                                                                               
    sorted_persons = sorted(
        registry,
        key=lambda x: (x.hop_class != 'unknown', x.score),
        reverse=True)
    for rank, p in enumerate(sorted_persons, 1):
        p.tier_rank = rank
    return sorted_persons
