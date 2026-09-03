"""Authenticated-viewer friendship-status aggregation.

chaining_cluster.json (Phase 26) sample'larinda her user icin friendship_status
dict bulunur (following / followed_by / outgoing_request / incoming_request /
blocking / is_restricted / is_bestie / muting / is_feed_favorite). Person
registry'de friendship_status zaten merge edilmis durumda. These flags always
describe the authenticated viewer and candidate X; they do not describe target
and X unless the authenticated viewer is the target account.

Ek olarak target_internal_phase33.json'daki friendships_show (target_pk icin
viewer<->target) okunur — bu sadece target_pk'nin Person record'u icin
ayrilmis bir slot olabilir, ama target_pk registry'de yer almaz (kendisi
hedef). Yine de target'in iliskileri intel raporunda yansitilir.
"""

from .loader import Artifacts
from .person import PersonRegistry


def _add_viewer_evidence(person, source: str, note: str):
    """Record viewer-scoped context without affecting target confidence."""
    person.add_evidence(source, 0, {
        'scope': 'authenticated_viewer_to_candidate',
        'note': note,
        'target_relationship_inferred': False,
    })


def ingest_friendship_grid(arts: Artifacts, registry: PersonRegistry):
    """Phase 28 baseline /info/'daki chaining_suggestions icindeki her user'in
    friendship_status dict'ini (TAM dolu — viewer<->X tum flag'ler) registry'ye
    yaz. Bu chaining_cluster sample'larinda BOS gelen veri."""
    import os, json
    path = os.path.join(arts.target_dir, 'phase28_baseline_info.raw.json')
    if not os.path.exists(path):
        return {'loaded': False, 'reason': 'no_baseline_raw'}
    try:
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {'loaded': False, 'reason': 'parse_error'}

    user = d.get('user') or {}
    if not isinstance(user, dict):
        return {'loaded': False, 'reason': 'invalid_target_user'}
    active_target_pk = arts.target_pk or arts.resolve_target_pk()
    artifact_target_pk = user.get('pk') or d.get('target_pk') or d.get('pk')
    if (active_target_pk is None or artifact_target_pk is None
            or str(active_target_pk) != str(artifact_target_pk)):
        return {'loaded': False, 'ignored': True,
                'reason': 'artifact_target_scope_missing_or_mismatch'}
    chain = (user.get('chaining_suggestions')
              or user.get('chaining_results') or [])
    if not chain:
        return {'loaded': False, 'reason': 'no_chaining_suggestions'}

    enriched = 0
    for u in chain:
        pk = u.get('pk')
        if not pk:
            continue
        p = registry.get_or_create(pk, u.get('username'))
        fs = u.get('friendship_status') or {}
        if isinstance(fs, dict):
            for k, v in fs.items():
                                                                    
                if k not in p.friendship_status:
                    p.friendship_status[k] = v
                    enriched += 1
                                                  
        if u.get('profile_pic_id') and not p.profile_pic_id:
            p.profile_pic_id = u['profile_pic_id']
        p.merge_full_name(u.get('full_name'))
        p.merge_flag('is_private', u.get('is_private'))
        p.merge_flag('is_verified', u.get('is_verified'))
    return {'loaded': True, 'rows': len(chain), 'enriched_fields': enriched,
            'friendship_scope': 'authenticated_viewer_to_candidate',
            'target_relationship_inferred': False}


def aggregate_friendship(registry: PersonRegistry):
    """Record viewer↔candidate status; never relabel it as target↔candidate."""
    counters = {'following': 0, 'followed_by': 0, 'outgoing_request': 0,
                 'incoming_request': 0, 'mutual': 0, 'blocking': 0,
                 'restricted': 0, 'bestie': 0, 'subscribed': 0,
                 'feed_favorite': 0, 'muting': 0}

    for p in registry:
        fs = p.friendship_status or {}
        if not fs:
            continue
        if fs.get('following'):
            _add_viewer_evidence(
                p, 'friendship_viewer_follows_candidate',
                'Authenticated viewer follows this candidate.')
            counters['following'] += 1
        if fs.get('followed_by'):
            _add_viewer_evidence(
                p, 'friendship_candidate_follows_viewer',
                'This candidate follows the authenticated viewer.')
            counters['followed_by'] += 1
        if fs.get('following') and fs.get('followed_by'):
            _add_viewer_evidence(
                p, 'friendship_viewer_candidate_mutual',
                'Viewer and candidate follow each other; target is not implied.')
            counters['mutual'] += 1
        if fs.get('outgoing_request'):
            _add_viewer_evidence(
                p, 'friendship_viewer_requested_candidate',
                'Authenticated viewer sent this candidate a follow request.')
            counters['outgoing_request'] += 1
        if fs.get('incoming_request'):
            _add_viewer_evidence(
                p, 'friendship_candidate_requested_viewer',
                'This candidate sent the authenticated viewer a follow request.')
            counters['incoming_request'] += 1
        if fs.get('blocking'):
            _add_viewer_evidence(
                p, 'friendship_viewer_blocks_candidate',
                'Authenticated viewer blocks this candidate.')
            counters['blocking'] += 1
        if fs.get('is_restricted'):
            _add_viewer_evidence(
                p, 'friendship_viewer_restricted_candidate',
                'Authenticated viewer restricted this candidate.')
            counters['restricted'] += 1
                                                                        
        if fs.get('is_bestie'):
            counters['bestie'] += 1
            _add_viewer_evidence(
                p, 'friendship_candidate_on_viewer_close_friends',
                'Candidate is on the authenticated viewer close-friends list.')
        if fs.get('subscribed'):
            counters['subscribed'] += 1
            _add_viewer_evidence(
                p, 'friendship_viewer_subscribed_candidate',
                'Authenticated viewer subscribes to this candidate.')
        if fs.get('is_feed_favorite'):
            counters['feed_favorite'] += 1
            _add_viewer_evidence(
                p, 'friendship_candidate_on_viewer_favorites',
                'Candidate is in the authenticated viewer Favorites feed.')
        if fs.get('muting'):
            counters['muting'] += 1
            _add_viewer_evidence(
                p, 'friendship_viewer_mutes_candidate',
                'Authenticated viewer mutes this candidate.')
    return {**counters,
            'scope': 'authenticated_viewer_to_candidate',
            'target_relationship_inferred': False}


def load_target_internal(arts: Artifacts):
    """target_internal_phase33.json'dan target ile iliski raporlamasi icin
    veriyi cek (registry'ye yazilmaz, ozet rapor icin)."""
    ti = arts.get('target_internal') or {}
    return {
        'friendships_show': ti.get('friendships_show'),
        'dm_thread': ti.get('dm_thread'),
    }
