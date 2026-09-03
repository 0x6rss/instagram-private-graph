"""Phase 29 archeology — target -> X (cluster) yonu.

archeology_phase29.json'dan likes/comments listelerini pk basina indexler.
'media_owner_pk/username' = X (cluster member); target hangi X'e etkilesim
yapmis ona yazariz.
"""

from .config import WEIGHTS
from .loader import Artifacts
from .person import PersonRegistry


def ingest_archeology(arts: Artifacts, registry: PersonRegistry):
    arch = arts.get('archeology_p29') or {}
    likes = arch.get('likes') or []
    comments = arch.get('comments') or []
    if not (likes or comments):
        return {'loaded': False, 'likes': 0, 'comments': 0}

    for like in likes:
        owner_pk = like.get('media_owner_pk')
        if not owner_pk:
            continue
        p = registry.get_or_create(owner_pk, like.get('media_owner_username'))
        p.likes_to_x.append({
            'media_id': like.get('media_id'),
            'media_url': like.get('media_url'),
            'taken_at_iso': like.get('media_taken_at_iso'),
            'taken_at_ts': like.get('media_taken_at_ts'),
            'caption_head': like.get('media_caption_head'),
        })
        ts = like.get('media_taken_at_ts')
        if isinstance(ts, (int, float)):
            p.activity_timestamps.append(int(ts))
        p.add_evidence('phase29_like', WEIGHTS['p29_like_per'], {
            'media_id': like.get('media_id'),
            'taken_at_iso': like.get('media_taken_at_iso'),
        })

    for c in comments:
        owner_pk = c.get('media_owner_pk')
        if not owner_pk:
            continue
        p = registry.get_or_create(owner_pk, c.get('media_owner_username'))
        p.comments_to_x.append({
            'media_id': c.get('media_id'),
            'media_url': c.get('media_url'),
            'comment_text': c.get('comment_text'),
            'comment_iso': c.get('comment_iso'),
            'comment_ts': c.get('comment_ts'),
            'comment_pk': c.get('comment_pk'),
        })
        ts = c.get('comment_ts') or c.get('media_taken_at_ts')
        if isinstance(ts, (int, float)):
            p.activity_timestamps.append(int(ts))
        p.add_evidence('phase29_comment', WEIGHTS['p29_comment_per'], {
            'media_id': c.get('media_id'),
            'comment_iso': c.get('comment_iso'),
            'text_head': (c.get('comment_text') or '')[:60],
        })

    return {'loaded': True,
            'likes': len(likes), 'comments': len(comments),
            'distinct_owners': len({l.get('media_owner_pk')
                                    for l in likes if l.get('media_owner_pk')}
                                   | {c.get('media_owner_pk')
                                      for c in comments
                                      if c.get('media_owner_pk')})}
