"""Phase 30 tagged_feed + Phase 26 tag_search ingestion.

X -> target yonu:
    - tagged_feed.direct.taggers — direkt /usertags/{pk}/feed/'den taggers
    - tagged_feed.cluster_pivot.taggers — cluster pivot taggers
    - tagged_feed.*.tags_found / items — tek tek tag postlari (co_tagged_users
      her postta target dahil olmadan diger tag'lenenler)
    - tag_search_cluster.tagged_posts_found — cluster public feed scan'inden
      target'i tag'leyen veya mention eden public hesap postlari
"""

from .config import WEIGHTS
from .loader import Artifacts
from .person import PersonRegistry


def _record_tagger(p, media_id):
    p.tags_of_target_count += 1
    if media_id and media_id not in p.tag_media_ids:
        p.tag_media_ids.append(str(media_id))
    p.add_evidence('phase30_tagger', WEIGHTS['p30_tagger_per'],
                    {'media_id': media_id})


def _record_co_tag(p, media_id):
    p.co_tag_count += 1
    if media_id and media_id not in p.co_tag_media_ids:
        p.co_tag_media_ids.append(str(media_id))
    p.add_evidence('phase30_co_tagged', WEIGHTS['p30_co_tagged_per'],
                    {'media_id': media_id})


def ingest_tagged_feed(arts: Artifacts, registry: PersonRegistry):
    tf = arts.get('tagged_feed') or {}
    if not tf:
        return {'loaded': False}

    counters = {'direct_taggers': 0, 'pivot_taggers': 0, 'co_tagged': 0,
                 'tag_posts': 0}

    direct = tf.get('direct') or {}
    direct_items = direct.get('items') or []

                                                                
    for item in direct_items:
        counters['tag_posts'] += 1
        tagger_pk = item.get('tagger_pk')
        media_id = item.get('media_id')
        if tagger_pk:
            tagger_un = item.get('tagger_username')
            p = registry.get_or_create(tagger_pk, tagger_un)
            p.merge_flag('is_private', item.get('tagger_is_private'))
            p.merge_flag('is_verified', item.get('tagger_is_verified'))
            _record_tagger(p, media_id)
            counters['direct_taggers'] += 1
            ts = item.get('taken_at_ts')
            if isinstance(ts, (int, float)):
                p.activity_timestamps.append(int(ts))
                                    
        for co in (item.get('co_tagged_users') or []):
            cpk = co.get('pk')
            if not cpk:
                continue
            cp = registry.get_or_create(cpk, co.get('username'))
            _record_co_tag(cp, media_id)
            counters['co_tagged'] += 1

                                                          
    pivot = tf.get('cluster_pivot') or {}
    pivot_tags = pivot.get('tags_found') or []
    for tag in pivot_tags:
        counters['tag_posts'] += 1
        tagger_pk = tag.get('tagger_pk')
        media_id = tag.get('media_id')
        if tagger_pk:
            tagger_un = tag.get('tagger_username')
            p = registry.get_or_create(tagger_pk, tagger_un)
            _record_tagger(p, media_id)
            counters['pivot_taggers'] += 1
            ts = tag.get('taken_at_ts')
            if isinstance(ts, (int, float)):
                p.activity_timestamps.append(int(ts))
        for co in (tag.get('co_tagged_users') or []):
            cpk = co.get('pk')
            if not cpk:
                continue
            cp = registry.get_or_create(cpk, co.get('username'))
            _record_co_tag(cp, media_id)
            counters['co_tagged'] += 1

    return {'loaded': True, **counters,
            'leaked_total_count': direct.get('leaked_total_count')}


def ingest_tag_search(arts: Artifacts, registry: PersonRegistry):
    """tag_search_cluster.json — cluster public feed'lerinde target tag/mention
    scan."""
    ts_data = arts.get('tag_search_cluster') or {}
    posts = ts_data.get('tagged_posts_found') or []
    if not posts and not ts_data.get('mention_accounts'):
        return {'loaded': False}

    via_count = {'usertag': 0, 'mention': 0}
    for post in posts:
        via = post.get('found_via') or 'usertag'
        via_count[via] = via_count.get(via, 0) + 1
        poster_pk = post.get('poster_pk')
        if not poster_pk:
            continue
        p = registry.get_or_create(poster_pk, post.get('poster_username'))
        p.merge_flag('is_private', post.get('poster_is_private'))
        p.tag_search_hits += 1
        if via == 'mention':
            p.mentioned_target = True
            p.add_evidence('phase26_tag_search_mention',
                            WEIGHTS['p30_mention_per'],
                            {'media_id': post.get('media_id'),
                             'caption_head': (post.get('caption') or '')[:80]})
        else:
            p.add_evidence('phase26_tag_search_tag',
                            WEIGHTS['p26_tag_search_per'],
                            {'media_id': post.get('media_id'),
                             'taken_at_iso': post.get('taken_at')})
        ts_p = post.get('taken_at')
                                                               

                                       
        for ut in (post.get('usertags_in_post') or []):
            cpk = ut.get('pk')
            if not cpk or str(cpk) == post.get('poster_pk'):
                continue
            cp = registry.get_or_create(cpk, ut.get('username'))
            _record_co_tag(cp, post.get('media_id'))

                                                     
    for acc in (ts_data.get('mention_accounts') or []):
        pk = acc.get('pk')
        if not pk:
            continue
        p = registry.get_or_create(pk, acc.get('username'))
                                                                          
               

    return {'loaded': True, 'posts': len(posts), **via_count,
            'mention_accounts_count': len(ts_data.get('mention_accounts') or [])}
