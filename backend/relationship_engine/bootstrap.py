"""Target-scoped bootstrap metadata enrichment.

Yanit semasi:
    {
      "surfaces": [
        {"name": "autocomplete_user_list", "scores": {pk: int 0-100}, ...},
        {"name": "coefficient_besties_list_ranking", "scores": {...}},
        {"name": "coefficient_rank_recipient_user_suggestion", ...},
        {"name": "coefficient_ios_section_test_bootstrap_ranking", ...},
        {"name": "coefficient_direct_recipients_ranking_variant_2", ...},
      ],
      "users": [{pk, username, full_name, is_private, is_verified, ...}, ...],
      "interest_keywords": [],
      "status": "ok"
    }

Bootstrap surfaces are bound to the authenticated viewer, not to an arbitrary
queried target. Global captures are therefore never ingested. Only target-local
captures that explicitly declare both ``target_pk`` and ``viewer_pk`` equal to
the active target may enrich candidates already discovered by target-scoped
sources. Bootstrap data never creates a target candidate and is not follower
proof or a calibrated probability.
"""

import glob
import json
import os

from .config import WEIGHTS
from .loader import Artifacts
from .person import PersonRegistry


                                                                          
                         
_SURFACE_TO_WEIGHT = {
    'coefficient_besties_list_ranking':              'bootstrap_besties_present',
    'coefficient_rank_recipient_user_suggestion':    'bootstrap_dm_recipient',
    'coefficient_direct_recipients_ranking_variant_2': 'bootstrap_dm_recipient',
    'coefficient_ios_section_test_bootstrap_ranking': 'bootstrap_section_test',
                                                                  
}

                              
_AUTOCOMPLETE_TOP_MIN = 70                       
_AUTOCOMPLETE_MID_MIN = 30                       


def _is_bootstrap_payload(d) -> bool:
    return (isinstance(d, dict)
            and isinstance(d.get('surfaces'), list)
            and isinstance(d.get('users'), list))


def _discover_capture_files(arts: Artifacts) -> list[str]:
    """Return target-local bootstrap captures only.

    ``relationship_engine/apiler`` is intentionally excluded because those
    captures have no reliable queried-target scope.
    """
    pattern = os.path.join(arts.target_dir, 'bootstrap_users*.json')
    return sorted(set(glob.glob(pattern)))


def _load_capture(path: str) -> dict | None:
    try:
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return d if _is_bootstrap_payload(d) else None


def _scope_value(payload: dict, key: str):
    """Read explicit scope metadata from supported capture envelopes."""
    for container in (payload, payload.get('scope'), payload.get('meta')):
        if isinstance(container, dict) and container.get(key) is not None:
            return container.get(key)
    return None


def _is_target_owned_capture(payload: dict, target_pk: str | None) -> bool:
    """Require explicit target ownership; directory placement is insufficient."""
    if target_pk is None:
        return False
    expected = str(target_pk)
    declared_target = _scope_value(payload, 'target_pk')
    viewer_pk = (_scope_value(payload, 'viewer_pk')
                 or _scope_value(payload, 'ds_user_id'))
    return (declared_target is not None and viewer_pk is not None
            and str(declared_target) == expected
            and str(viewer_pk) == expected)


def _autocomplete_weight_key(score: int) -> str:
    if score >= _AUTOCOMPLETE_TOP_MIN:
        return 'bootstrap_autocomplete_top'
    if score >= _AUTOCOMPLETE_MID_MIN:
        return 'bootstrap_autocomplete_mid'
    return 'bootstrap_autocomplete_tail'


def ingest_bootstrap_users(arts: Artifacts, registry: PersonRegistry,
                             target_pk: str | None = None) -> dict:
    """Enrich existing candidates from explicitly target-owned captures."""
    capture_paths = _discover_capture_files(arts)
    if not capture_paths:
        return {'loaded': False, 'reason': 'no_target_local_capture_files',
                'searched': [arts.target_dir],
                'global_captures_ignored': True}

                                                                                    
    pk_stats: dict[str, dict] = {}
    pk_profile: dict[str, dict] = {}                                          
    surfaces_seen: dict[str, int] = {}                                              
    captures_loaded: list[str] = []
    captures_rejected: list[str] = []

    for path in capture_paths:
        d = _load_capture(path)
        if d is None:
            captures_rejected.append(os.path.basename(path))
            continue
        if not _is_target_owned_capture(d, target_pk):
            captures_rejected.append(os.path.basename(path))
            continue
        captures_loaded.append(os.path.basename(path))

                                          
        for u in (d.get('users') or []):
            if not isinstance(u, dict):
                continue
            pk = u.get('pk')
            if pk is None:
                continue
            pk_s = str(pk)
                                                                     
            cur = pk_profile.get(pk_s)
            if cur is None or (not cur.get('full_name') and u.get('full_name')):
                pk_profile[pk_s] = u

                        
        for surf in (d.get('surfaces') or []):
            if not isinstance(surf, dict):
                continue
            name = surf.get('name') or ''
            scores = surf.get('scores') or {}
            if not isinstance(scores, dict) or not scores:
                continue
            surfaces_seen[name] = surfaces_seen.get(name, 0) + 1
                                                                      
            ranked = []
            for scored_pk, raw_score in scores.items():
                try:
                    score = max(0, min(100, int(raw_score or 0)))
                except (TypeError, ValueError):
                    continue
                ranked.append((scored_pk, score))
            ranked.sort(key=lambda kv: -kv[1])
            for rank, (pk, score) in enumerate(ranked):
                pk_s = str(pk)
                st = pk_stats.setdefault(pk_s, {
                    'surfaces': {},                                              
                    'capture_files': set(),
                })
                                                       
                cur = st['surfaces'].get(name)
                if cur is None or score > cur['score']:
                    st['surfaces'][name] = {
                        'score': score,
                        'rank': rank,
                        'total': len(ranked),
                    }
                st['capture_files'].add(os.path.basename(path))

                                                                            
                                                               
    scoped_pool_size = len(pk_stats)
    candidates_enriched = 0
    candidates_ignored = 0
    target_in_pool = False
    target_score = None
    for pk_s, st in pk_stats.items():
        prof = pk_profile.get(pk_s, {})
        person = registry.by_pk(pk_s)
        if person is None:
            candidates_ignored += 1
            continue
        person.merge_username(prof.get('username'))
        person.merge_full_name(prof.get('full_name'))
        person.merge_flag('is_private', prof.get('is_private'))
        person.merge_flag('is_verified', prof.get('is_verified'))
        if prof.get('profile_pic_url') and not person.profile_pic_url:
            person.profile_pic_url = prof['profile_pic_url']
        if prof.get('profile_pic_id') and not person.profile_pic_id:
            person.profile_pic_id = prof['profile_pic_id']

        person.bootstrap_present = True
        person.bootstrap_surfaces = sorted(st['surfaces'].keys())
        scores_list = [s['score'] for s in st['surfaces'].values()]
        ranks_list = [s['rank'] for s in st['surfaces'].values()]
        person.bootstrap_max_score = max(scores_list) if scores_list else None
        person.bootstrap_avg_rank = (round(sum(ranks_list) / len(ranks_list), 2)
                                       if ranks_list else None)
        person.bootstrap_capture_count = len(st['capture_files'])

                                    
        for name, info in st['surfaces'].items():
            if name == 'autocomplete_user_list':
                wkey = _autocomplete_weight_key(info['score'])
            else:
                wkey = _SURFACE_TO_WEIGHT.get(name, 'bootstrap_section_test')
            person.add_evidence(f'bootstrap_{name}', WEIGHTS[wkey], {
                'surface': name,
                'score': info['score'],
                'rank': info['rank'],
                'total_in_surface': info['total'],
                'weight_key': wkey,
                'scope': 'target_is_authenticated_viewer',
                'note': ('Target-owned algorithmic affinity signal; not proof '
                         'of a follower/following edge.'),
            })
                             
        if person.bootstrap_capture_count >= 2:
            person.add_evidence('bootstrap_multi_capture',
                                  WEIGHTS['bootstrap_multi_capture_bonus'], {
                                      'capture_count': person.bootstrap_capture_count,
                                      'scope': 'target_is_authenticated_viewer',
                                      'note': ('Repeated target-owned algorithmic '
                                               'visibility; not calibrated certainty.'),
                                  })

        candidates_enriched += 1
        if target_pk and pk_s == str(target_pk):
            target_in_pool = True
            target_score = person.bootstrap_max_score

                                                                                
    coverage = {
        'pool_size': scoped_pool_size,
        'matched_existing_candidates': candidates_enriched,
        'ignored_new_candidates': candidates_ignored,
        'is_follower_coverage': False,
    }
    if target_pk and target_in_pool:
        coverage['target_in_bootstrap_pool'] = True
        coverage['target_max_score'] = target_score

    return {
        'loaded': bool(captures_loaded),
        'reason': (None if captures_loaded else
                   'no_capture_with_matching_target_and_viewer_scope'),
        'captures_loaded': captures_loaded,
        'captures_count': len(captures_loaded),
        'captures_rejected': captures_rejected,
        'unique_pks': scoped_pool_size,
        'candidates_enriched': candidates_enriched,
        'new_candidates_ignored': candidates_ignored,
        'global_captures_ignored': True,
        'surfaces_with_scores': surfaces_seen,
        'coverage': coverage,
    }
