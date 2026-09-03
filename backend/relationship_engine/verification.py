"""Heuristic 1-hop model-confidence scoring.

The calculation compares two binomial visibility models for repeated,
current-run recommendation-list observations. Its constants and uniform prior
are not calibrated against representative follower ground truth, and calls are
not guaranteed to be independent. The output is therefore an algorithmic
confidence indicator, not a measured probability, certainty, or proof of a
follow relationship.

Historical API fields such as ``probability_1hop`` and display labels such as
``verified`` remain for compatibility. ``unknown`` means no valid model input
and must remain distinct from a measured low/noise result.
"""

import math

from .person import PersonRegistry


                                                                   
P1_HOP_VISIBILITY = 0.70
P2_HOP_VISIBILITY = 0.16


def _binom_pmf(k: int, n: int, p: float) -> float:
    """C(n,k) * p^k * (1-p)^(n-k)"""
    if n <= 0 or k < 0 or k > n:
        return 0.0
    return (math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k)))


def bayesian_p_1hop(seen_count: int, total_runs: int) -> float:
    """Return 0..1 confidence under the configured visibility model.

    Invalid observations are rejected rather than silently clamped; clamping a
    corrupted count previously turned it into a near-certain-looking result.
    """
    if isinstance(seen_count, bool) or isinstance(total_runs, bool):
        return 0.0
    try:
        seen_count = int(seen_count)
        total_runs = int(total_runs)
    except (TypeError, ValueError):
        return 0.0
    if total_runs <= 0 or seen_count < 0 or seen_count > total_runs:
        return 0.0

    L1 = _binom_pmf(seen_count, total_runs, P1_HOP_VISIBILITY)
    L2 = _binom_pmf(seen_count, total_runs, P2_HOP_VISIBILITY)
    if L1 + L2 == 0:
        return 0.0
    return L1 / (L1 + L2)


                                                                      
HOP_CLASS_THRESHOLDS = [
    ('verified',           0.99),
    ('high_probability',   0.80),
    ('medium_probability', 0.40),
    ('low_probability',    0.15),
    ('noise',              0.0),
]


def classify_by_probability(prob: float) -> str:
    for label, thr in HOP_CLASS_THRESHOLDS:
        if prob >= thr:
            return label
    return 'noise'


def _positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _validated_count(value, total: int) -> tuple[int, bool]:
    """Return (count, valid) without inflating or clamping malformed input."""
    if isinstance(value, bool):
        return 0, False
    try:
        count = int(value or 0)
    except (TypeError, ValueError):
        return 0, False
    if count < 0 or count > total:
        return 0, False
    return count, True


def classify_hop(registry: PersonRegistry, sweep_n: int = 15,
                  total_p32: int = 80, multi_run: int = 1):
    """Calculate a backward-compatible, uncalibrated confidence score.

    Phase 32 uses unique current-session run visibility. Phase 28 is considered
    only when it has a current-run snapshot and Phase 32 did not observe the
    person. Viewer-global bootstrap, Banyan, and reciprocal recommendations do
    not override this score.
    """
    sweep_n = _positive_int(sweep_n, 15)
    multi_run = _positive_int(multi_run, 1)
    total_p32 = _positive_int(total_p32, 80)
    counters = {label: 0 for label, _ in HOP_CLASS_THRESHOLDS}
    counters['unknown'] = 0
    invalid_p28_counts = 0
    invalid_p32_counts = 0

    for p in registry:
        p28_count, p28_valid = _validated_count(
            p.cluster_module_count, sweep_n)
        p32_count, p32_valid = _validated_count(
            p.phase32_seen_runs_count, multi_run)
        if not p28_valid:
            invalid_p28_counts += 1
        if not p32_valid:
            invalid_p32_counts += 1

                               
        p32_prob = (bayesian_p_1hop(p32_count, multi_run)
                     if p32_valid and p32_count > 0 else 0.0)
                                                               
                                                                   
        p28_prob = 0.0
        if p32_count == 0 and p28_valid and p28_count > 0:
                                                                       
                                                                     
                                                                        
            L1 = _binom_pmf(p28_count, sweep_n, 0.5)
            L2 = _binom_pmf(p28_count, sweep_n, 0.07)
            if L1 + L2 > 0:
                p28_prob = L1 / (L1 + L2)

        prob = max(p32_prob, p28_prob)

                                                                              
                                                                            
                                                                   
        n_story = p.story_mentioned_by_target_count
        if p.story_collab_with_target:
                                                                          
            prob = max(prob, 0.97)
        elif n_story >= 3:
            prob = max(prob, 0.95)                          
        elif n_story == 2:
            prob = max(prob, 0.88)                          
        elif n_story == 1:
            prob = max(prob, 0.80)                
                                                                       
                                                                       
        if (n_story > 0 or p.story_collab_with_target) and (
                p.tags_of_target_count or p.co_tag_count
                or p.mentioned_target):
            prob = max(prob, 0.95)

        p.probability_1hop = round(prob * 100, 2)

                                                                               
                                                    
        has_independent_signal = (
            p.story_mentioned_by_target_count > 0
            or p.story_collab_with_target
        )
        if ((not p32_valid or p32_count == 0)
                and (not p28_valid or p28_count == 0)
                and not has_independent_signal):
            hop = 'unknown'
        else:
            hop = classify_by_probability(prob)
        p.hop_class = hop
        counters[hop] = counters.get(hop, 0) + 1

                                
        combined = p28_count + p32_count
        total_calls = sweep_n + multi_run
        p.combined_presence_count = combined
        p.combined_presence_ratio = round(
            min(1.0, combined / total_calls) if total_calls > 0 else 0, 4)

                  
        all_ranks = [r for r in (p.phase32_all_ranks or [])
                     if isinstance(r, (int, float))
                     and not isinstance(r, bool)]
        avg_rank = (sum(all_ranks) / len(all_ranks)) if all_ranks else None
        p.add_evidence(f'verification_{hop}', 0, {
            'p32_seen_count': p32_count,
            'p32_total_runs': multi_run,
            'p32_seen_ratio': (round(min(1.0, p32_count / multi_run), 3)
                               if p32_valid and multi_run else 0),
            'p32_observation_valid': p32_valid,
            'p32_avg_rank': round(avg_rank, 2) if avg_rank is not None else None,
            'p28_module_count': p28_count,
            'p28_sweep_n': sweep_n,
            'p28_observation_valid': p28_valid,
            'bayesian_P_1hop_p32': round(p32_prob * 100, 2),
            'bayesian_P_1hop_p28': round(p28_prob * 100, 2),
            'final_probability_1hop_pct': p.probability_1hop,
            'final_model_confidence_pct': p.probability_1hop,
            'score_semantics': 'uncalibrated_model_confidence',
            'hop_label': hop,
        })

    return {
        'counts': counters,
        'sweep_n': sweep_n, 'multi_run': multi_run,
        'total_calls': sweep_n + multi_run,
        'total_p32': total_p32,
        'invalid_p28_counts': invalid_p28_counts,
        'invalid_p32_counts': invalid_p32_counts,
        'algorithm': 'bayesian_visibility_heuristic_v4',
        'score_semantics': 'uncalibrated_model_confidence',
        'priors': {
            'P_1hop': 0.5,
            'P_2hop': 0.5,
            'P_visibility_1hop': P1_HOP_VISIBILITY,
            'P_visibility_2hop': P2_HOP_VISIBILITY,
        },
        'hop_class_thresholds': dict(HOP_CLASS_THRESHOLDS),
        'note': ('Score is an uncalibrated model-confidence indicator. Legacy '
                 'tier names do not prove identity, intimacy, or a follower/'
                 'following edge.'),
    }


                                              
LEGACY_HOP_LABELS = {
    'verified':           '1hop_stable',
    'high_probability':   '1hop_strong',
    'medium_probability': '1hop_confirmed',
    'low_probability':    '1hop_likely',
    'noise':              '2hop_suspect',
    'unknown':            'unknown',
}
