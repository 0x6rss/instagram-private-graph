"""Group uncalibrated model-confidence scores into display tiers.

``unknown`` remains separate from numeric low/noise output so missing evidence
is not presented as negative evidence.
"""

from .config import TIER_THRESHOLDS
from .person import PersonRegistry


def classify(registry: PersonRegistry):
    counts = {name: 0 for name, _ in TIER_THRESHOLDS}
    counts.setdefault('unknown', 0)
    for p in registry:
                                                                            
                                                                             
                                                        
        if p.hop_class == 'unknown':
            p.tier = 'unknown'
            counts['unknown'] += 1
            continue
        for name, threshold in TIER_THRESHOLDS:
            if p.score >= threshold:
                p.tier = name
                counts[name] += 1
                break
    return counts


def by_tier(registry: PersonRegistry):
    grouped: dict[str, list] = {name: [] for name, _ in TIER_THRESHOLDS}
    grouped.setdefault('unknown', [])
    for p in registry:
        if p.tier:
            grouped.setdefault(p.tier, []).append(p)
                                       
    for tier in grouped:
        grouped[tier].sort(key=lambda x: -x.score)
    return grouped
