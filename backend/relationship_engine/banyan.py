"""Phase 37 target-owned share-sheet affinity enrichment.

IG'nin share-sheet endpoint'i (faceswap_share_sheet, post_share_sheet, vb.) 10
farklı view'da viewer'in en sik etkilesimli kisilerini ML-ranked donduruyor.
Bu Phase 32 chaining'in farkli bir algoritmik oneriler boyutudur; chaining de
Banyan da takip listesini veya takip yonunu kanitlamaz.

Phase 37 cikti formati:
  target_in_views: [{view, rank, total_in_view, ...}]
  all_ranked_users: { pk: {username, full_name, views: [...], best_rank} }

Share-sheet rankings are authenticated-viewer data. They may enrich an existing
candidate only when the artifact explicitly proves ``viewer_pk == target_pk``
and its target scope matches the active target. They never discover candidates,
prove a follow edge, or directly override model confidence.
"""

from .loader import Artifacts
from .person import PersonRegistry


def ingest_banyan(arts: Artifacts, registry: PersonRegistry):
    bd = arts.get('banyan_phase37') or {}
    if not isinstance(bd, dict) or not bd:
        return {'loaded': False, 'reason': 'no_artifact'}

    active_target_pk = arts.target_pk or arts.resolve_target_pk()
    artifact_target_pk = bd.get('target_pk')
    viewer_pk = bd.get('viewer_pk')
    if active_target_pk is None:
        return {'loaded': False, 'ignored': True,
                'reason': 'active_target_pk_missing'}
    if artifact_target_pk is None or str(artifact_target_pk) != str(active_target_pk):
        return {'loaded': False, 'ignored': True,
                'reason': 'artifact_target_scope_mismatch',
                'viewer_scoped_metadata_only': True}
    if viewer_pk is None or str(viewer_pk) != str(active_target_pk):
        return {'loaded': False, 'ignored': True,
                'reason': 'viewer_is_not_target_or_scope_missing',
                'viewer_scoped_metadata_only': True}

    all_ranked = bd.get('all_ranked_users') or {}
    if not isinstance(all_ranked, dict):
        return {'loaded': False, 'ignored': True,
                'reason': 'invalid_ranked_users'}
    target_view_count = bd.get('target_view_count') or 0
    counts = {
        'views_tested': bd.get('views_tested') or 0,
        'views_with_data': bd.get('views_with_data') or 0,
        'total_ranked_users': len(all_ranked),
        'target_view_count': target_view_count,
        'candidates_enriched': 0,
        'new_candidates_ignored': 0,
    }

                                                                    
    for pk, info in all_ranked.items():
        if not pk or not isinstance(info, dict):
            continue
        p = registry.by_pk(pk)
        if p is None:
            counts['new_candidates_ignored'] += 1
            continue
        p.merge_username(info.get('username'))
        p.merge_full_name(info.get('full_name'))
        p.merge_flag('is_private', info.get('is_private'))
        p.merge_flag('is_verified', info.get('is_verified'))
        view_names = [v.get('view') for v in (info.get('views') or [])
                      if isinstance(v, dict) and v.get('view')]
        p.banyan_views = list(dict.fromkeys((p.banyan_views or []) + view_names))
        p.banyan_view_count = len(p.banyan_views)
        if info.get('best_rank') is not None:
            try:
                best_rank = int(info['best_rank'])
            except (TypeError, ValueError):
                best_rank = None
            if (best_rank is not None and best_rank >= 0
                    and (p.banyan_best_rank is None
                         or best_rank < p.banyan_best_rank)):
                p.banyan_best_rank = best_rank
        counts['candidates_enriched'] += 1

                                                          
                                            
        if p.banyan_view_count >= 3:
            p.add_evidence('phase37_banyan_strong', 30, {
                'view_count': p.banyan_view_count,
                'views': p.banyan_views[:5],
                'best_rank': p.banyan_best_rank,
                'scope': 'target_is_authenticated_viewer',
                'note': ('Repeated target-owned share-sheet visibility is an '
                         'algorithmic affinity signal, not follow proof.'),
            })
        elif p.banyan_view_count >= 1:
            p.add_evidence('phase37_banyan_present', 12, {
                'view_count': p.banyan_view_count,
                'views': p.banyan_views,
                'best_rank': p.banyan_best_rank,
                'scope': 'target_is_authenticated_viewer',
                'note': ('Target-owned share-sheet visibility is an algorithmic '
                         'affinity signal, not follow proof.'),
            })

    return {'loaded': True,
            'scope': 'target_is_authenticated_viewer', **counts}
