"""Phase 35 reciprocal recommendation-list co-occurrence ingest.

Seeing X in the target's chaining suggestions and the target in X's chaining
suggestions is bidirectional algorithmic co-occurrence. It does not expose the
follower graph and cannot establish follow direction or mutual-follow status.
"""

from .loader import Artifacts
from .person import PersonRegistry


def ingest_reciprocal(arts: Artifacts, registry: PersonRegistry):
    rd = arts.get('reciprocal_phase35') or {}
    if not isinstance(rd, dict):
        return {'loaded': False, 'reason': 'invalid_artifact'}
    if rd.get('error'):
        return {'loaded': False, 'reason': rd['error']}
    active_target_pk = arts.target_pk or arts.resolve_target_pk()
    artifact_target_pk = rd.get('target_pk')
    if (active_target_pk is None or artifact_target_pk is None
            or str(active_target_pk) != str(artifact_target_pk)):
        return {'loaded': False, 'ignored': True,
                'reason': 'artifact_target_scope_missing_or_mismatch'}
    results = rd.get('reciprocal_results') or []
    if not results:
        return {'loaded': False, 'reason': 'no_results'}

    counts = {'bidirectional_cooccurrence': 0, 'one_way_cooccurrence': 0,
              'legacy_follow_claims_discarded': 0, 'errors': 0}

    for r in results:
        if not isinstance(r, dict):
            counts['errors'] += 1
            continue
        pk = r.get('cluster_pk')
        if not pk:
            counts['errors'] += 1
            continue
        if r.get('error') or r.get('http_status') and r.get('http_status') != 200:
            counts['errors'] += 1
            continue
        p = registry.get_or_create(pk, r.get('cluster_username'))
        p.reciprocal_checked = True
        p.reciprocal_target_in_their_chain = bool(r.get('target_in_their_chain'))
        p.target_rank_in_their_chain = r.get('target_rank_in_their_chain')
        p.their_chain_size = r.get('their_chain_size')
        reverse_seen = bool(r.get('target_in_their_chain'))
        relation_label = ('BIDIRECTIONAL_RECOMMENDATION_OVERLAP'
                          if reverse_seen
                          else 'ONE_WAY_RECOMMENDATION_ONLY')
        p.inferred_relationship = relation_label
                            
        if r.get('cluster_full_name') and not p.full_name:
            p.full_name = r['cluster_full_name']

        if r.get('inferred_relationship'):
            counts['legacy_follow_claims_discarded'] += 1

        if reverse_seen:
            counts['bidirectional_cooccurrence'] += 1
            p.add_evidence('phase35_bidirectional_chain_cooccurrence', 0, {
                'target_rank_in_their_chain': r.get('target_rank_in_their_chain'),
                'their_chain_size': r.get('their_chain_size'),
                'note': ('Target and candidate appeared in each other\'s '
                         'recommendation context; no follow direction is proven.'),
            })
        else:
            counts['one_way_cooccurrence'] += 1
            p.add_evidence('phase35_one_way_chain_cooccurrence', 0, {
                'note': ('Candidate was tested from the target recommendation '
                         'pool, but reverse visibility was not observed. This '
                         'does not establish follow direction.'),
            })

    return {'loaded': True, 'tested': len(results), **counts,
            'semantics': 'recommendation_cooccurrence_not_follow_graph'}
