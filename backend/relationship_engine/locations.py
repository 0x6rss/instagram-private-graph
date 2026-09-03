"""Location cross-correlation.

tagged_feed.cluster_pivot.tags_found ve tag_search_cluster.tagged_posts_found
icindeki her tag posttaki location.pk + location.name + city + lat/lng
toplanir. Ayni location'da iki farkli pk varsa, fiziksel ortak yer kanitidir
(aile/arkadas grubu).

Burada strateji: location_id basina (target ile birlikte tag'lendigi) tum X
pk'larini toplama. >1 farkli kisinin paylastigi location 'shared physical
location' olarak isaretlenir; pk'lar shared_locations alanina yazilir +
score eklenir.
"""

from .config import WEIGHTS
from .loader import Artifacts
from .person import PersonRegistry


def _extract_location_data(arts: Artifacts) -> list[dict]:
    """Her tag-post icin {'tagger_pk', 'co_pks', 'location'} dict listesi."""
    out = []

    tf = arts.get('tagged_feed') or {}
    direct_items = (tf.get('direct') or {}).get('items') or []
    for it in direct_items:
        loc = it.get('location') or {}
        if loc.get('pk') or loc.get('name'):
            out.append({
                'tagger_pk': str(it.get('tagger_pk') or ''),
                'co_pks': [str(c.get('pk') or '')
                           for c in (it.get('co_tagged_users') or [])
                           if c.get('pk')],
                'location': loc,
                'media_id': it.get('media_id'),
                'taken_at_iso': it.get('taken_at_iso'),
            })

    pivot_tags = (tf.get('cluster_pivot') or {}).get('tags_found') or []
    for tag in pivot_tags:
        loc = tag.get('location') or {}
        if loc.get('pk') or loc.get('name'):
            out.append({
                'tagger_pk': str(tag.get('tagger_pk') or ''),
                'co_pks': [str(c.get('pk') or '')
                           for c in (tag.get('co_tagged_users') or [])
                           if c.get('pk')],
                'location': loc,
                'media_id': tag.get('media_id'),
                'taken_at_iso': tag.get('taken_at_iso'),
            })

    ts_data = arts.get('tag_search_cluster') or {}
    for post in (ts_data.get('tagged_posts_found') or []):
        loc_name = post.get('location')
        if loc_name:
            out.append({
                'tagger_pk': str(post.get('poster_pk') or ''),
                'co_pks': [str(ut.get('pk') or '')
                           for ut in (post.get('usertags_in_post') or [])
                           if ut.get('pk')],
                'location': {'name': loc_name},
                'media_id': post.get('media_id'),
                'taken_at_iso': post.get('taken_at'),
            })

    return out


def analyze(arts: Artifacts, registry: PersonRegistry, target_pk: str):
    posts = _extract_location_data(arts)
    if not posts:
        return {'loaded': False, 'posts': 0}

                                                          
    by_loc: dict[str, dict] = {}
    target_pk_s = str(target_pk) if target_pk else ''
    for post in posts:
        loc = post['location']
        key = str(loc.get('pk') or '') or 'name:' + str(loc.get('name', ''))
        if key not in by_loc:
            by_loc[key] = {'location': loc, 'pks': set(), 'media_ids': set()}
                                                                            
                                                                    
        if post['tagger_pk']:
            by_loc[key]['pks'].add(post['tagger_pk'])
        for cp in post['co_pks']:
            if cp:
                by_loc[key]['pks'].add(cp)
        if post.get('media_id'):
            by_loc[key]['media_ids'].add(post['media_id'])

    counters = {'loaded': True, 'distinct_locations': len(by_loc),
                 'shared_locations': 0, 'persons_attributed': 0}

    for loc_key, info in by_loc.items():
        pks = info['pks'] - {target_pk_s}
        if not pks:
            continue
        loc_summary = {
            'pk': info['location'].get('pk'),
            'name': info['location'].get('name'),
            'city': info['location'].get('city'),
            'lat': info['location'].get('lat'),
            'lng': info['location'].get('lng'),
            'media_count': len(info['media_ids']),
        }
        if len(pks) >= 1:
            counters['shared_locations'] += 1
        for pk in pks:
            p = registry.get_or_create(pk)
            p.shared_locations.append(loc_summary)
            p.add_evidence('shared_location_with_target',
                            WEIGHTS['same_location_per'],
                            {'location_name': loc_summary['name'],
                             'location_pk': loc_summary['pk'],
                             'media_count': loc_summary['media_count']})
            counters['persons_attributed'] += 1

    return counters
