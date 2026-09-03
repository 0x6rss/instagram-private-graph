"""Phase 32 — discover_chaining_phase32.json ingestion.

Cluster_union'a phase32 merge ediliyor olsa da, discover_chaining_phase32.json
direkt okumak Phase 32 spesifik metadata'yi (full_name, profile_pic_id,
context_class, **rank**) kanit olarak kayda gecirmemizi saglar.

The response is an algorithmic recommendation list. ``real_connection`` and
rank are useful model features, but neither proves a follower edge. Percentile
buckets are retained for backward-compatible evidence and must be interpreted
as uncalibrated association signals.
"""

from .config import (P32_RANK_MID_PCT, P32_RANK_TOP_PCT, WEIGHTS)
from .loader import Artifacts
from .person import PersonRegistry


def _matches_active_target(arts: Artifacts, payload: dict) -> bool:
    active_pk = arts.target_pk or arts.resolve_target_pk()
    artifact_pk = payload.get('target_pk') or payload.get('pk')
    return (active_pk is not None and artifact_pk is not None
            and str(active_pk) == str(artifact_pk))


def _positive_int(value, default: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _valid_rank(value, cap: int = 80) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        rank = int(value)
    except (TypeError, ValueError):
        return None
    return rank if 0 <= rank < cap else None


def _normalise_run_observations(user: dict, total_runs: int,
                                fallback_rank: int | None):
    """Return one optional rank per valid, unique Phase 32 run ID.

    Older writers could append the same PK twice in one run. Counting that raw
    list inflated confidence and could yield a seen ratio above 1. Invalid or
    out-of-range IDs are ignored. A legacy row without IDs counts as only one
    observation because its presence proves one call at minimum.
    """
    raw_runs = user.get('_seen_runs')
    raw_ranks = user.get('_all_ranks')
    ranks = raw_ranks if isinstance(raw_ranks, list) else []

                                                                          
                                                                           
                      
    if user.get('_current_session_seen') is False:
        return {}, 0, 0, False

    if not isinstance(raw_runs, list) or not raw_runs:
                                                                         
                                                                           
                                                   
        if '_current_session_seen' not in user:
            return ({0: fallback_rank} if total_runs > 0 else {}), 0, 0, True
        return {}, 0, 1, False

    by_run: dict[int, int | None] = {}
    duplicate_refs = 0
    invalid_refs = 0
    for idx, raw_run in enumerate(raw_runs):
        if isinstance(raw_run, bool):
            invalid_refs += 1
            continue
        try:
            run_id = int(raw_run)
        except (TypeError, ValueError):
            invalid_refs += 1
            continue
        if run_id < 0 or run_id >= total_runs:
            invalid_refs += 1
            continue

        rank = _valid_rank(ranks[idx]) if idx < len(ranks) else None
        if run_id in by_run:
            duplicate_refs += 1
            old_rank = by_run[run_id]
            if rank is not None and (old_rank is None or rank < old_rank):
                by_run[run_id] = rank
        else:
            by_run[run_id] = rank
    return by_run, duplicate_refs, invalid_refs, False


def _rank_bucket_for_real(rank: int, total: int) -> tuple[str, float]:
    """rank → (bucket_name, weight). total = API'nin dondurdugu toplam user."""
    if total <= 0:
        return 'mid', WEIGHTS['p32_real_mid']
    pct = rank / total
    if pct < P32_RANK_TOP_PCT:
        return 'top', WEIGHTS['p32_real_top']
    if pct < P32_RANK_MID_PCT:
        return 'mid', WEIGHTS['p32_real_mid']
    return 'tail', WEIGHTS['p32_real_tail']


def ingest_discover_p32(arts: Artifacts, registry: PersonRegistry):
    p32 = arts.get('discover_p32') or {}
    if not isinstance(p32, dict):
        return {'loaded': False, 'reason': 'invalid_artifact'}
    if not _matches_active_target(arts, p32):
        return {'loaded': False, 'ignored': True,
                'reason': 'artifact_target_scope_missing_or_mismatch'}
    users = p32.get('users') or []
    if not isinstance(users, list) or not users:
        return {'loaded': False}

                                                                           
                                                                             
                                                   
                                                                          
    SINGLE_CALL_CAP = 80
    total = SINGLE_CALL_CAP

                                                                           
                                                                      
    multi_run_count = _positive_int(
        p32.get('this_session_runs') or p32.get('multi_run_count'), 1)

    counts = {'real_connection': 0, 'suggested': 0, 'other': 0,
              'no_context': 0,
              'rank_top': 0, 'rank_mid': 0, 'rank_tail': 0,
              'duplicate_run_refs_removed': 0,
              'invalid_run_refs_removed': 0,
              'legacy_run_fallback_users': 0,
              'historical_archive_users_unscored': 0}
    observations_by_pk: dict[str, dict[int, int | None]] = {}

    for list_idx, u in enumerate(users):
        if not isinstance(u, dict):
            continue
        pk = u.get('pk')
        if not pk:
            continue
        p = registry.get_or_create(pk, u.get('username'))
        p.merge_full_name(u.get('full_name'))
        p.merge_flag('is_private', u.get('is_private'))
        p.merge_flag('is_verified', u.get('is_verified'))
                                                                           
                                                 
        historical_archive = u.get('_current_session_seen') is False
        rank = _valid_rank(u.get('_first_seen_rank'), SINGLE_CALL_CAP)
        if rank is None and not historical_archive:
            rank = list_idx if list_idx < SINGLE_CALL_CAP else None
        if p.phase32_rank is None and rank is not None:
            p.phase32_rank = rank

                                                                               
                                        
        run_map, duplicate_refs, invalid_refs, used_legacy_fallback = (
            _normalise_run_observations(u, multi_run_count, rank))
        counts['duplicate_run_refs_removed'] += duplicate_refs
        counts['invalid_run_refs_removed'] += invalid_refs
        if used_legacy_fallback:
            counts['legacy_run_fallback_users'] += 1
        if historical_archive:
            counts['historical_archive_users_unscored'] += 1
        pk_s = str(pk)
        combined_runs = observations_by_pk.setdefault(pk_s, {})
        for run_id, observed_rank in run_map.items():
            old_rank = combined_runs.get(run_id)
            if (run_id not in combined_runs
                    or (observed_rank is not None
                        and (old_rank is None or observed_rank < old_rank))):
                combined_runs[run_id] = observed_rank
        p.phase32_seen_runs_count = min(multi_run_count, len(combined_runs))
        all_ranks = [r for _, r in sorted(combined_runs.items())
                     if r is not None]
        if all_ranks:
            p.phase32_all_ranks = all_ranks
            p.phase32_avg_rank = round(sum(all_ranks) / len(all_ranks), 2)
            p.phase32_min_rank = min(all_ranks)
            p.phase32_max_rank = max(all_ranks)

        ctx = u.get('context_class') or 'no_context'
        counts[ctx] = counts.get(ctx, 0) + 1
        p.context_class = p.context_class or ctx
        p.social_context = p.social_context or u.get('social_context')
        p.profile_chaining_secondary_label = (
            p.profile_chaining_secondary_label
            or u.get('profile_chaining_secondary_label'))

        if u.get('profile_pic_id') and not p.profile_pic_id:
            p.profile_pic_id = u['profile_pic_id']
        if u.get('profile_pic_url') and not p.profile_pic_url:
            p.profile_pic_url = u['profile_pic_url']

                                                                    
        if historical_archive:
            p.add_evidence('phase32_historical_archive_unscored', 0, {
                'note': ('Historical candidate/profile retained without '
                         'current-session visibility confidence.'),
            })
        elif ctx == 'real_connection' or ctx == 'other':
                                                                               
            effective_rank = rank if rank is not None else SINGLE_CALL_CAP - 1
            bucket, weight = _rank_bucket_for_real(effective_rank, total)
            rank = effective_rank
            counts[f'rank_{bucket}'] += 1
            rank_pct = round(rank / total, 3) if total else None
            p.add_evidence(f'phase32_real_{bucket}', weight,
                            {'rank': rank,
                             'total_users': total,
                             'rank_pct': rank_pct,
                             'rank_bucket': bucket,
                             'social_context': u.get('social_context'),
                             'full_name': u.get('full_name'),
                             'is_private': u.get('is_private'),
                             'is_verified': u.get('is_verified'),
                             'context_class': ctx,
                             'note': ('Percentile bucket in an algorithmic '
                                      'recommendation list. This is a model '
                                      'signal, not proof of a follow edge.')})
        elif ctx == 'suggested':
            p.add_evidence('phase32_suggested',
                            WEIGHTS['p32_only_suggested'],
                            {'rank': rank, 'total_users': total,
                             'note': ('Algorithmic suggestion only; it does not '
                                      'establish a personal or follow relationship.')})
        else:              
            p.add_evidence('phase32_no_context',
                            WEIGHTS['p32_no_context'],
                            {'rank': rank, 'total_users': total})

        if u.get('is_verified'):
            p.add_evidence('phase32_is_verified',
                            WEIGHTS['is_verified_penalty'],
                            {'reason': 'public_figure_not_personal'})

    return {'loaded': True, 'users': len(users), 'cap_used': total,
            'multi_run_count': multi_run_count, **counts,
            'rank_top_pct': P32_RANK_TOP_PCT,
            'rank_mid_pct': P32_RANK_MID_PCT,
            'effective_rank_top_max': int(total * P32_RANK_TOP_PCT),
            'effective_rank_mid_max': int(total * P32_RANK_MID_PCT)}
