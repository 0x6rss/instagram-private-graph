"""Phase 28 cluster_union + Phase 26 chaining_cluster ingestion.

cluster_union.json dort bucket'a sahip:
    stable_inner_circle (15/15)
    strong_signal (>=75%)
    weak_sampled
    cluster (raw union — pk -> {username, source_modules})

chaining_cluster.json — Phase 26 extended_bearer suggested_users (chaining_score,
mutual_followers_count, friendship_status, follower/following counts dolu).
"""

from .config import WEIGHTS
from .loader import Artifacts
from .person import PersonRegistry


def _matches_active_target(arts: Artifacts, payload: dict) -> bool:
    """Reject unscoped/mismatched artifacts before mutating the registry."""
    active_pk = arts.target_pk or arts.resolve_target_pk()
    artifact_pk = payload.get('target_pk') or payload.get('pk')
    return (active_pk is not None and artifact_pk is not None
            and str(active_pk) == str(artifact_pk))


def ingest_cluster_union(arts: Artifacts, registry: PersonRegistry):
    cu = arts.get('cluster_union') or {}
    if not isinstance(cu, dict) or not cu:
        return {'loaded': False}
    if not _matches_active_target(arts, cu):
        return {'loaded': False, 'ignored': True,
                'reason': 'artifact_target_scope_missing_or_mismatch'}

                                                                     
                                                                             
                                                                         
                                                                              
                                                                        
    current_cluster = cu.get('current_run_cluster')
    current_run_scoped = isinstance(current_cluster, dict)
    cluster = current_cluster if current_run_scoped else (cu.get('cluster') or {})
    if not isinstance(cluster, dict):
        return {'loaded': False, 'reason': 'invalid_cluster'}

    try:
        sweep_n = int(cu.get('sweep_modules_count') or 15)
    except (TypeError, ValueError):
        sweep_n = 15
    sweep_n = max(1, sweep_n)
    threshold_stable = sweep_n
    threshold_strong = max(1, int(sweep_n * 0.75))

    counts = {'stable': 0, 'strong': 0, 'weak': 0,
              'legacy_unscored': 0, 'invalid_module_counts': 0,
              'pks': len(cluster)}

    for pk, info in cluster.items():
        if not isinstance(info, dict):
            continue
        p = registry.get_or_create(pk, info.get('username'))
        raw_modules = info.get('source_modules') or []
        if not isinstance(raw_modules, (list, tuple, set)):
            raw_modules = []
                                                                               
                                                                              
                                                
        modules = list(dict.fromkeys(
            str(m) for m in raw_modules
            if (m is not None and str(m)
                and not str(m).startswith('phase32_discover'))
        ))
        if not p.cluster_modules:
            p.cluster_modules = list(modules)
                                                  
        p.merge_full_name(info.get('full_name'))
        p.merge_flag('is_private', info.get('is_private'))
        p.merge_flag('is_verified', info.get('is_verified'))
        if info.get('social_context') and not p.social_context:
            p.social_context = info['social_context']
        if info.get('context_class') and not p.context_class:
            p.context_class = info['context_class']

        if not current_run_scoped:
                                                                              
                                                              
            p.cluster_module_count = None
            p.add_evidence('phase28_legacy_history_unscored', 0, {
                'historical_modules': modules,
                'historical_count': len(modules),
                'note': ('Legacy merged history retained as candidate metadata; '
                         'it is not current-run repeatability evidence.'),
            })
            counts['legacy_unscored'] += 1
            continue

        n = len(modules)
        if n > sweep_n:
                                                                         
                                                          
            counts['invalid_module_counts'] += 1
            n = sweep_n
        p.cluster_module_count = n
        if n >= threshold_stable:
            p.add_evidence('phase28_stable_15_15',
                            WEIGHTS['stable_inner_15_15'],
                            {'modules': modules, 'count': n,
                             'scope': 'current_run',
                             'note': 'Repeated recommendation-model visibility; not follow proof.'})
            counts['stable'] += 1
        elif n >= threshold_strong:
            p.add_evidence('phase28_strong_signal',
                            WEIGHTS['strong_signal_75pct'],
                            {'modules': modules, 'count': n,
                             'threshold': threshold_strong,
                             'scope': 'current_run',
                             'note': 'Repeated recommendation-model visibility; not follow proof.'})
            counts['strong'] += 1
        else:
            p.add_evidence('phase28_weak_sampled',
                            WEIGHTS['weak_sampled'],
                            {'modules': modules, 'count': n,
                             'scope': 'current_run',
                             'note': 'Single-run algorithmic visibility.'})
            counts['weak'] += 1

    return {'loaded': True, **counts,
            'sweep_n': sweep_n,
            'threshold_strong': threshold_strong,
            'observation_scope': ('current_run' if current_run_scoped
                                  else 'legacy_history_unscored')}


def ingest_chaining_cluster(arts: Artifacts, registry: PersonRegistry):
    """Phase 26 extended_bearer 80-user dump.

    User objects can include follower/media counts plus viewer-scoped
    ``mutual_followers_count`` and ``friendship_status``. Viewer-scoped values
    are never relabelled as target relationships. MFC becomes target-relative
    only when the artifact explicitly records ``viewer_pk == target_pk``.
    """
    cc = arts.get('chaining_cluster') or {}
    if not isinstance(cc, dict) or not _matches_active_target(arts, cc):
        return {'loaded': False, 'ignored': True,
                'reason': 'artifact_target_scope_missing_or_mismatch'}
    active_target_pk = arts.target_pk or arts.resolve_target_pk()
    viewer_pk = cc.get('viewer_pk')
    viewer_is_target = (viewer_pk is not None
                        and str(viewer_pk) == str(active_target_pk))
    users = cc.get('users') or []
    if not isinstance(users, list) or not users:
        return {'loaded': False}

    enriched = 0
    fs_count = 0
    for u in users:
        if not isinstance(u, dict):
            continue
        pk = u.get('pk')
        if not pk:
            continue
        p = registry.get_or_create(pk, u.get('username'))
        p.merge_full_name(u.get('full_name'))
        p.merge_flag('is_private', u.get('is_private'))
                                                  
        for attr, key in (('follower_count', 'follower_count'),
                           ('following_count', 'following_count'),
                           ('media_count', 'media_count'),
                           ('chaining_score', 'chaining_score')):
            v = u.get(key)
            if v is not None and getattr(p, attr) is None:
                setattr(p, attr, v)
                enriched += 1

                                                                          
                                                                              
                                                                            
                                                          
        mfc = u.get('mutual_followers_count')
        if (viewer_is_target and isinstance(mfc, int)
                and not isinstance(mfc, bool) and mfc >= 0
                and p.mutual_followers_count is None):
            p.mutual_followers_count = mfc
            enriched += 1
        elif mfc is not None and not viewer_is_target:
            p.add_evidence('viewer_mutual_followers_metadata', 0, {
                'count': mfc,
                'scope': 'authenticated_viewer_to_candidate',
                'target_relationship_inferred': False,
            })

                                            
        fs = u.get('friendship_status') or {}
        if isinstance(fs, dict) and fs:
                                                
            for k, v in fs.items():
                if k not in p.friendship_status:
                    p.friendship_status[k] = v
            fs_count += 1

                                     
        chain_detail = {
            'chaining_score': u.get('chaining_score'),
            'scope': 'target_recommendation_response',
            'note': 'Algorithmic recommendation visibility; not follow proof.',
        }
        if viewer_is_target and p.mutual_followers_count is not None:
            chain_detail['target_mutual_followers_count'] = (
                p.mutual_followers_count)
        p.add_evidence('phase26_chaining_cluster',
                        WEIGHTS['p26_chain_present'],
                        chain_detail)

                                                                    
        cs = u.get('chaining_score')
        if isinstance(cs, (int, float)) and cs >= 0.4:
            p.add_evidence('phase26_chaining_score_high',
                            WEIGHTS['p26_chaining_score_high'],
                            {'chaining_score': cs})

    return {'loaded': True, 'users': len(users),
            'enriched_fields': enriched,
            'with_friendship_status': fs_count,
            'viewer_pk_present': viewer_pk is not None,
            'viewer_is_target': viewer_is_target,
            'friendship_scope': 'authenticated_viewer_to_candidate',
            'mutual_followers_scope': (
                'target_to_candidate' if viewer_is_target
                else 'viewer_metadata_only')}
