"""Phase 38 — STORY MENTIONS ingestion.

Source: GET /api/v1/feed/user/{target_pk}/story/  (raw IG response).

Yon: target -> X. target X'i story'sinde mention etmis (reel_mention sticker,
bloks_mention, question response), birlikte collab post yapmis veya story'de
ayni location'i paylasmis. Phase 29 (likes/comments) ile ayni yondeyiz ama
story mention DELIBERATE bir paylasimdir (24h gecici, gorunur, kisisel) —
rastgele bir like'tan kuvvetli intimacy isaretidir.

Sema (single reel):
    {
      "reel": {
        "id": "<owner_pk>",
        "user": {pk, username, full_name, is_private, is_verified, ...},
        "items": [
          {
            "id": "<media_id>_<owner_pk>",
            "pk": ...,
            "taken_at": <unix_ts>,
            "expiring_at": <unix_ts>,
            "reel_mentions": [
              {"x":..,"y":..,"user":{"pk":..,"username":..,"full_name":..}, ...}
            ],
            "story_bloks_stickers": [
              {"bloks_sticker_id":"...mention...","sticker_data":{"ig_mention":{"account_id":..,"username":..}}}
            ],
            "story_locations": [
              {"location":{"pk":..,"short_name":..,"name":..,"lat":..,"lng":..}}
            ],
            "story_music_stickers": [
              {"music_asset_info":{"audio_cluster_id":..,"display_artist":..,"ig_username":..}}
            ],
            "story_questions": [
              {"question_response_id": ..., "responses_count": ..., "x":..,"y":..,
               "question_sticker":{"profile_pic_url":..,"text":..}}
            ],
            "fundraiser_id_for_story": ...,
            "story_app_attribution": {"id":..,"name":..,"profile_pic_url":..,...},
            "shopping_metadata": {...},
            "story_brand_partner_users": [{"id":..,"username":..}],
            "story_collab": {"collaborators":[{"pk":..,"username":..}], ...},
            "image_versions2": ..., "media_type": 1|2, ...
          }
        ],
        "expiring_at": ...
      },
      "status": "ok"
    }

Batch sema (reels query yapildiysa):
    {"reels": {pk_str: reel_obj}, ...}  -> her reel'in items'i parse edilir.

Engine target_pk'yi resolve eder; reel.user.pk == target_pk olan reel'leri
isler (yanlis hedefli yedek dosya gondererek false-positive yaratma riskini
azaltir).
"""

from .config import WEIGHTS
from .loader import Artifacts
from .person import PersonRegistry


def _iter_items(payload, target_pk: str | None):
    """Raw IG response'dan (reel veya reels) story item dict'lerini yield et.

    target_pk verilmisse SADECE owner'i target_pk olan reel'lerin item'lari
    yield edilir (yanlis hedefli kaydedilen dosya icin guvenlik)."""
    if not isinstance(payload, dict):
        return

    candidates = []
    reel = payload.get('reel')
    if isinstance(reel, dict):
        candidates.append(reel)
    reels = payload.get('reels')
    if isinstance(reels, dict):
        candidates.extend(v for v in reels.values() if isinstance(v, dict))
                                  
    tray = payload.get('tray')
    if isinstance(tray, list):
        candidates.extend(t for t in tray if isinstance(t, dict))

    for r in candidates:
        owner = (r.get('user') or {}).get('pk') or r.get('id')
        if target_pk and str(owner or '') != str(target_pk):
            continue
        for item in (r.get('items') or []):
            if isinstance(item, dict):
                yield item


def _add_mention(p, kind: str, media_id, taken_at):
    p.story_mentioned_by_target_count += 1
    if media_id and str(media_id) not in p.story_mention_media_ids:
        p.story_mention_media_ids.append(str(media_id))
    p.story_mention_kinds.append(kind)
    if isinstance(taken_at, (int, float)):
        p.activity_timestamps.append(int(taken_at))
    p.add_evidence('phase38_story_mention', WEIGHTS['story_mention_per'], {
        'media_id': media_id,
        'kind': kind,
        'taken_at_ts': taken_at if isinstance(taken_at, (int, float)) else None,
    })


def ingest_story_mentions(arts: Artifacts, registry: PersonRegistry,
                            target_pk: str | None = None) -> dict:
    payload = arts.get('story_phase38')
    if not isinstance(payload, dict):
        return {'loaded': False}

    counters = {
        'items_seen': 0,
        'reel_mentions': 0,
        'bloks_mentions': 0,
        'question_responses': 0,
        'collab_partners': 0,
        'brand_partners': 0,
        'app_attributions': 0,
        'distinct_mentioned_pks': 0,
        'locations': 0,
    }
    mentioned_pks = set()
    locations_collected = []

    for item in _iter_items(payload, target_pk):
        counters['items_seen'] += 1
        media_id = item.get('id') or item.get('pk')
        taken_at = item.get('taken_at')

                                                              
        for rm in (item.get('reel_mentions') or []):
            user = rm.get('user') or {}
            pk = user.get('pk')
            if not pk or (target_pk and str(pk) == str(target_pk)):
                continue
            p = registry.get_or_create(pk, user.get('username'))
            p.merge_full_name(user.get('full_name'))
            p.merge_flag('is_private', user.get('is_private'))
            p.merge_flag('is_verified', user.get('is_verified'))
            _add_mention(p, 'reel_mention', media_id, taken_at)
            counters['reel_mentions'] += 1
            mentioned_pks.add(str(pk))

                                                                                  
        for bs in (item.get('story_bloks_stickers') or []):
            sd = (bs.get('sticker_data') or {})
            mention = sd.get('ig_mention') or {}
            pk = mention.get('account_id')
            if not pk or (target_pk and str(pk) == str(target_pk)):
                continue
            p = registry.get_or_create(pk, mention.get('username'))
            _add_mention(p, 'bloks_mention', media_id, taken_at)
            counters['bloks_mentions'] += 1
            mentioned_pks.add(str(pk))

                                                                               
                                                                           
                                                                               
                                                                             
                                 
        for q in (item.get('story_questions') or []):
            if q.get('question_response_id'):
                counters['question_responses'] += 1

                                                
        collab = item.get('story_collab') or {}
        for c in (collab.get('collaborators') or []):
            pk = c.get('pk') or c.get('id')
            if not pk or (target_pk and str(pk) == str(target_pk)):
                continue
            p = registry.get_or_create(pk, c.get('username'))
            p.merge_full_name(c.get('full_name'))
            p.story_collab_with_target = True
            p.add_evidence('phase38_story_collab',
                            WEIGHTS['story_collab_per'],
                            {'media_id': media_id, 'taken_at_ts': taken_at})
            counters['collab_partners'] += 1
            mentioned_pks.add(str(pk))

                                                                  
        for bp in (item.get('story_brand_partner_users') or []):
            pk = bp.get('id') or bp.get('pk')
            if not pk or (target_pk and str(pk) == str(target_pk)):
                continue
            p = registry.get_or_create(pk, bp.get('username'))
            _add_mention(p, 'brand_partner', media_id, taken_at)
            counters['brand_partners'] += 1
            mentioned_pks.add(str(pk))

                                                                         
        att = item.get('story_app_attribution') or {}
        att_pk = att.get('id')
        if att_pk and att_pk != target_pk:
            counters['app_attributions'] += 1

                                                                
        for loc in (item.get('story_locations') or []):
            l = loc.get('location') or {}
            if not l.get('pk'):
                continue
            entry = {
                'pk': l.get('pk'),
                'name': l.get('name') or l.get('short_name'),
                'lat': l.get('lat'), 'lng': l.get('lng'),
                'media_id': media_id,
                'taken_at_ts': taken_at,
            }
            locations_collected.append(entry)
            counters['locations'] += 1

                                                                  
    repeat_bonus_applied = 0
    for pk in mentioned_pks:
        p = registry.by_pk(pk)
        if p and p.story_mentioned_by_target_count >= 2:
            p.add_evidence('phase38_story_mention_repeat',
                            WEIGHTS['story_mention_repeat_bonus'], {
                                'count': p.story_mentioned_by_target_count,
                                'media_ids': p.story_mention_media_ids[:5],
                            })
            repeat_bonus_applied += 1

    counters['distinct_mentioned_pks'] = len(mentioned_pks)
    counters['repeat_bonus_applied'] = repeat_bonus_applied

                                                                          
                                                                              
                         
    return {'loaded': True, **counters,
             'target_story_locations': locations_collected[:50]}
