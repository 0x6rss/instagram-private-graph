"""Target hakkinda toplanan tum metadata'yi konsolide et + multi-signal
geographic inference.

Kaynaklar:
  - presence_intel.json   (Phase 26): bearer_bypass, rest_presence, inbox,
                                       search, non_ui_fields, story_timing
  - target_internal_phase33.json     : friendships_show, dm_thread,
                                        search_typeahead, cdn_forensics, meta_ids,
                                        profile_pic_id_decode, html_ssr,
                                        info_business_contact, hidden_persona,
                                        bio_links_full, about_section_extended,
                                        highlights_tray, geo_signals, fb_resolution
  - dsa_transparency.json  (Phase 27): former_usernames, account_creation_*
  - cross_platform_bypass.json       : Threads profile, FB Graph results
  - archeology_phase29.json (Phase 29): target'in cluster'a etkilesim timeline'i

Cikti: tek bir target_intel dict, web UI tarafinda kategori-kategori gosterilir.
"""

from .loader import Artifacts
from . import geo_inference


def _safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def build_target_intel(arts: Artifacts) -> dict:
    pi = arts.get('presence_intel') or {}
    ti = arts.get('target_internal') or {}
    dsa = arts.get('dsa_transparency') or {}
                                                                                       
    import json
    import os
    cp_path = os.path.join(arts.target_dir, 'cross_platform_bypass.json')
    cp_data = {}
    if os.path.exists(cp_path):
        try:
            with open(cp_path, encoding='utf-8') as f:
                cp_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass

    arch = arts.get('archeology_p29') or {}

    out = {
        'identity':         _identity(pi, ti),
        'account_creation': _account_creation(pi, ti, dsa),
        'profile':          _profile(pi, ti),
        'privacy':          _privacy(pi, ti),
        'behavior_toggles': _behavior_toggles(pi, ti, arts),
        'personal_prefs':   _personal_prefs(pi, ti, arts),
        'monetization':     _monetization(pi, ti, arts),
        'friendship_grid':  _friendship_grid(arts),
        'leaked_counts':    _leaked_counts(arts),
        'geographic':       _geographic(pi, ti),
        'geo_inference':    geo_inference.build_geo_inference(arts),
        'dm_state':         _dm_state(pi, ti),
        'friendship':       _friendship(ti),
        'avatar':           _avatar(pi, ti),
        'story_highlights': _story_highlights(pi, ti),
        'birthday_oracle':  _birthday(pi),
        'bio_links':        ti.get('bio_links_full') or [],
        'meta_ids':         _meta_ids(pi, ti),
        'fb_resolution':    ti.get('fb_resolution') or {},
        'cross_platform':   _cross_platform(cp_data),
        'recovery':         _recovery(ti),
        'header_forensics': _safe_get(ti, 'response_header_forensics') or {},
        'cdn_forensics':    ti.get('cdn_forensics') or {},
        'thread_context_items':
            _safe_get(ti, 'dm_thread', 'thread_context_items') or [],
        'extras': _hidden_extras(pi, ti),
    }
    return out


def _identity(pi, ti) -> dict:
    nuf = _safe_get(pi, 'non_ui_fields', 'found_fields') or {}
    hp = ti.get('hidden_persona') or {}
    ssr = ti.get('html_ssr') or {}
    return {
        'pk': pi.get('pk') or ti.get('pk'),
        'username': ssr.get('canonical_url', '').rstrip('/').split('/')[-1] or None,
        'full_name': ssr.get('full_name'),
        'biography': ssr.get('biography'),
        'eimu_id': nuf.get('eimu_id') or hp.get('eimu_id'),
        'fbid_v2': nuf.get('fbid_v2'),
        'interop_messaging_user_fbid': nuf.get('interop_messaging_user_fbid'),
        'account_type': nuf.get('account_type') or hp.get('account_type'),
        'is_business': ssr.get('is_business'),
        'is_professional_account': ssr.get('is_professional_account'),
    }


def _account_creation(pi, ti, dsa) -> dict:
    out = {}
                                                                        
    dj = (_safe_get(pi, 'rest_presence', 'thread_participants',
                     'target_from_thread', 'date_joined')
          or _safe_get(ti, 'dm_thread', 'target_user.date_joined'))
    dj_iso = (_safe_get(pi, 'rest_presence', 'thread_participants',
                         'target_from_thread', 'date_joined_iso'))
    if dj:
        out['date_joined_unix'] = dj
    if dj_iso:
        out['date_joined_iso'] = dj_iso

                      
    definitive = dsa.get('definitive') or {}
    for k in ('account_creation_country', 'account_creation_country_text',
              'account_creation_year_month', 'joined_year_month_text',
              'former_usernames', 'account_takeover_count',
              'shared_followers_count'):
        v = definitive.get(k)
        if v:
            out[k] = v

                                     
    about = ti.get('about_section_extended') or {}
    for k in ('account_creation_country', 'account_creation_year_month',
              'former_usernames', 'name_changes_count',
              'account_age_month', 'has_run_ads', 'has_run_political_ads'):
        v = about.get(k)
        if v not in (None, '', [], {}):
            out[k] = v
    return out


def _profile(pi, ti) -> dict:
    bc = ti.get('info_business_contact') or {}
    ssr = ti.get('html_ssr') or {}
    out = dict(bc)                                           
                                                                       
    for k in ('full_name', 'biography', 'category_name', 'category',
              'follower_count', 'following_count', 'media_count',
              'og_follower_count', 'og_following_count', 'og_media_count',
              'business_email', 'business_phone_number', 'public_email',
              'public_phone_number', 'public_phone_country_code',
              'external_url', 'connected_fb_page',
              'biography_email_addresses', 'biography_phone_numbers',
              'bio_emails_extracted', 'bio_phones_extracted',
              'og_description', 'og_image', 'page_title'):
        v = ssr.get(k)
        if v not in (None, '', [], {}):
            out[k] = v
                                                            
    tci = _safe_get(ti, 'dm_thread', 'thread_context_items')
    if tci:
        out['thread_context_items'] = tci
    return out


def _privacy(pi, ti) -> dict:
    nuf = _safe_get(pi, 'non_ui_fields', 'found_fields') or {}
    ssr = ti.get('html_ssr') or {}
    target_from_thread = _safe_get(pi, 'rest_presence',
                                     'thread_participants',
                                     'target_from_thread') or {}
    return {
        'is_private': (target_from_thread.get('is_private')
                        if 'is_private' in target_from_thread
                        else ssr.get('is_private')),
        'is_verified': ssr.get('is_verified'),
        'has_anonymous_profile_picture': nuf.get('has_anonymous_profile_picture'),
        'has_private_collections': nuf.get('has_private_collections'),
        'is_in_eu': nuf.get('is_in_eu'),
        'is_in_canada': nuf.get('is_in_canada'),
        'show_post_insights_entry_point': nuf.get('show_post_insights_entry_point'),
        'show_account_transparency_details': nuf.get(
            'show_account_transparency_details'),
    }


def _geographic(pi, ti) -> dict:
    out = dict(ti.get('geo_signals') or {})
                                           
    rec = ti.get('recovery_probe') or {}
    if rec.get('lookup_user_country'):
        out['lookup_user_country'] = rec['lookup_user_country']
    return out


def _dm_state(pi, ti) -> dict:
    bc = _safe_get(pi, 'bearer_bypass', 'thread_context') or {}
    dm = ti.get('dm_thread') or {}
    target_pk = pi.get('pk') or ti.get('pk')
    reach = (bc.get('reachability_statuses') or
             dm.get('reachability_statuses') or {})
    target_reach = reach.get(str(target_pk)) if target_pk else None
    out = {
        'is_viewer_unconnected': bc.get('is_viewer_unconnected'),
        'responsiveness_category': bc.get('responsiveness_category')
            or dm.get('responsiveness_category'),
        'should_show_safety_card': bc.get('should_show_safety_card'),
        'has_reached_message_request_limit':
            dm.get('has_reached_message_request_limit'),
        'is_appointment_booking_enabled':
            dm.get('is_appointment_booking_enabled'),
        'reachability_status_code': target_reach,
        'reachability_status_meaning': {
            0: 'messageable', 1: 'message_request', 2: 'blocked',
        }.get(target_reach, f'unknown({target_reach})')
            if target_reach is not None else None,
    }

                                     
    inbox = pi.get('inbox') or {}
    for label in ('primary', 'pending', 'relevant'):
        e = inbox.get(label) or {}
        if e.get('thread_id'):
            out['existing_dm_thread'] = {
                'inbox': label,
                'thread_id': e.get('thread_id'),
                'thread_v2_id': e.get('thread_v2_id'),
                'last_permanent_item_iso': e.get('last_permanent_item_iso'),
                'last_activity_iso': e.get('last_activity_iso'),
                'last_seen_at_per_user': e.get('last_seen_at_per_user'),
                'last_item_user_pk': e.get('last_item_user_pk'),
                'last_item_type': e.get('last_item_type'),
                'last_item_text_head': e.get('last_item_text_head'),
                'inviter_pk': e.get('inviter_pk'),
                'muted': e.get('muted'),
                'marked_as_unread': e.get('marked_as_unread'),
            }
            break

                     
    rest = pi.get('rest_presence') or {}
    for label in ('rest_get_bracket', 'rest_get', 'rest_post', 'active_now'):
        e = rest.get(label) or {}
        tp = e.get('target_presence') or {}
        if tp:
            out['live_presence'] = {
                'is_active': tp.get('is_active'),
                'in_threads': tp.get('in_threads'),
                'last_activity_iso': tp.get('last_activity_iso'),
                'seconds_since_active': tp.get('seconds_since_active'),
                'source': label,
            }
            break

    return out


def _friendship(ti) -> dict:
    fs = ti.get('friendships_show') or {}
    if isinstance(fs, dict) and 'status' in fs:
                              
        return {k: v for k, v in fs.items() if k != 'status'}
    return fs if isinstance(fs, dict) else {}


def _avatar(pi, ti) -> dict:
    out = {}
    decode = (ti.get('profile_pic_id_decode')
              or _safe_get(pi, 'non_ui_fields', 'pic_id_decode'))
    if decode:
        out.update(decode)
    if ti.get('profile_pic_url'):
        out['profile_pic_url'] = ti['profile_pic_url']
    return out


def _story_highlights(pi, ti) -> dict:
    htray = ti.get('highlights_tray') or {}
    out = {
        'highlight_count': htray.get('highlight_count'),
        'highlights': htray.get('highlights') or [],
    }

                            
    st = pi.get('story_timing') or {}
    timings = []
    for label, e in (st or {}).items():
        if not isinstance(e, dict):
            continue
        if e.get('present') or e.get('latest_reel_media') or e.get('item_count'):
            timings.append({
                'endpoint': label,
                'latest_reel_media_iso': e.get('latest_reel_media_iso')
                    or e.get('newest_item_iso'),
                'expiring_at_iso': e.get('expiring_at_iso'),
                'highlight_count': e.get('highlight_count'),
                'item_count': e.get('item_count'),
            })
    if timings:
        out['timing_endpoints'] = timings
    return out


def _birthday(pi) -> dict:
    bo = _safe_get(pi, 'non_ui_fields', 'birthday_oracle') or {}
    return bo


def _meta_ids(pi, ti) -> dict:
    nuf = _safe_get(pi, 'non_ui_fields', 'found_fields') or {}
    mids = ti.get('meta_ids') or {}
    out = dict(mids)
    for k in ('eimu_id', 'fbid_v2', 'interop_messaging_user_fbid',
              'threads_profile_glyph_url'):
        v = nuf.get(k)
        if v and k not in out:
            out[k] = v
    return out


def _cross_platform(cp_data) -> dict:
    if not cp_data:
        return {}
    out = {}
    th = (cp_data.get('th_user_info') or {}).get('threads_user')
    if th:
        out['threads_user'] = th
    th_fl = cp_data.get('th_followers') or {}
    if th_fl.get('count'):
        out['threads_followers_count'] = th_fl['count']
    th_fo = cp_data.get('th_following') or {}
    if th_fo.get('count'):
        out['threads_following_count'] = th_fo['count']
    th_p = cp_data.get('th_user_threads') or {}
    if th_p.get('item_count'):
        out['threads_post_count'] = th_p['item_count']
    return out


def _recovery(ti) -> dict:
    r = ti.get('recovery_probe') or {}
    keys = ('obfuscated_email', 'obfuscated_phone', 'has_valid_phone',
            'has_whatsapp_installed', 'can_email_reset', 'can_sms_reset',
            'fb_login_option', 'has_fb_account_linked',
            'is_facebook_only_account', 'two_factor_required',
            'gdpr_required', 'gdpr_consent_required',
            'lookup_user_country', 'rate_limited')
    return {k: r[k] for k in keys if k in r}


def _hidden_extras(pi, ti) -> dict:
    """UI'da hic gosterilmeyen non-UI alanlar."""
    nuf = _safe_get(pi, 'non_ui_fields', 'found_fields') or {}
    interesting = (
        'professional_conversion_suggested_account_type',
        'qa_freeform_banner_available_prompts',
        'qa_freeform_banner_transparency',
        'has_private_collections',
        'show_post_insights_entry_point',
        'nametag',
        'fan_club_info',
        'meta_verified_benefits_info',
        'live_subscription_status', 'posts_subscription_status',
        'reels_subscription_status', 'stories_subscription_status',
        'highlights_tray_type',
        'recs_from_friends',
    )
    out = {k: nuf[k] for k in interesting if k in nuf and nuf[k]
           not in (None, '', [], {}, False, 0)}
    return out


                                                                             
                                        
                                                                             

def _behavior_toggles(pi, ti, arts) -> dict:
    """Phase 28 raw /info/'dan privacy + behavior switch'leri. UI bunlari hic
    gostermez ama API her response'ta yansitir."""
    nuf = _safe_get(pi, 'non_ui_fields', 'found_fields') or {}
    hp = ti.get('hidden_persona') or {}
    raw_user = _load_baseline_user(arts)

    out = {}
    BEHAVIOR_KEYS = (
        'auto_expand_chaining',                                                          
        'has_chaining',                                                
        'recs_from_friends',                                              
        'include_direct_blacklist_status',                              
        'views_on_grid_status',                                           
        'is_profile_picture_expansion_enabled',
        'is_profile_broadcast_sharing_enabled',
        'is_direct_roll_call_enabled',
        'can_message_pinned_carrera_interest_owner',
        'can_reply_to_profile_banners',
        'can_hide_category',
        'can_hide_public_contacts',
        'open_external_url_with_in_app_browser',
        'has_views_fetching',
        'has_public_tab_threads',
        'show_account_transparency_details',
        'show_post_insights_entry_point',
        'show_text_post_app_badge',
        'show_text_post_app_switcher_badge',
        'show_ig_app_switcher_badge',
        'show_mentions_banner_on_profile',
        'should_show_tagged_tab',
        'allow_manage_memorialization',
    )
    for k in BEHAVIOR_KEYS:
        v = nuf.get(k)
        if v is None:
            v = hp.get(k)
        if v is None and raw_user:
            v = raw_user.get(k)
        if v is not None:
            out[k] = v
    return out


def _personal_prefs(pi, ti, arts) -> dict:
    """Q&A banner prompts, nametag emoji, custom theme — kisisel tercihler."""
    nuf = _safe_get(pi, 'non_ui_fields', 'found_fields') or {}
    raw_user = _load_baseline_user(arts)
    out = {}

                         
    qa_prompts = nuf.get('qa_freeform_banner_available_prompts') or []
    if not qa_prompts and raw_user:
        qa_prompts = raw_user.get('qa_freeform_banner_available_prompts') or []
    if qa_prompts:
        out['qa_banner_prompts'] = [
            {'prompt': p.get('prompt'), 'display_text': p.get('display_text')}
            for p in qa_prompts if isinstance(p, dict)
        ]
    qt = (nuf.get('qa_freeform_banner_transparency')
          or (raw_user or {}).get('qa_freeform_banner_transparency'))
    if qt:
        out['qa_banner_transparency'] = qt

             
    nt = nuf.get('nametag') or (raw_user or {}).get('nametag') or {}
    if isinstance(nt, dict) and nt:
        out['nametag'] = {
            'emoji': nt.get('emoji'),
            'emoji_color': nt.get('emoji_color'),
            'selected_theme_color': nt.get('selected_theme_color'),
            'gradient': nt.get('gradient'),
            'mode': nt.get('mode'),
            'background_image_url': nt.get('background_image_url'),
            'is_background_image_blurred':
                nt.get('is_background_image_blurred'),
            'available_theme_colors': nt.get('available_theme_colors'),
        }

                     
    po = (nuf.get('profile_overlay_info')
          or (raw_user or {}).get('profile_overlay_info') or {})
    if po and po.get('overlay_format') and po.get('overlay_format') != 'NONE':
        out['profile_overlay'] = po

                                        
    for k in ('pronouns', 'gender', 'account_badges'):
        v = (raw_user or {}).get(k)
        if v not in (None, '', [], {}):
            out[k] = v

                   
    av = (raw_user or {}).get('avatar_status')
    if av:
        out['avatar_status'] = av
    return out


def _monetization(pi, ti, arts) -> dict:
    """Subscription, creator, fan club, fundraiser, Meta Verified status."""
    nuf = _safe_get(pi, 'non_ui_fields', 'found_fields') or {}
    raw_user = _load_baseline_user(arts)
    out = {}
    KEYS = (
        'live_subscription_status', 'posts_subscription_status',
        'reels_subscription_status', 'stories_subscription_status',
        'is_eligible_for_meta_verified_label',
        'is_eligible_for_meta_verified_subscription',
        'is_eligible_for_meta_verified_account_security_purchase',
        'is_meta_verified_subscription_holder',
        'meta_verified_benefits_info',
        'not_meta_verified_friction_info',
        'fan_club_info', 'creator_subscription_information',
        'subscription_information', 'paid_partnership_status',
        'has_subscription_offers', 'has_active_lead_form',
        'active_standalone_fundraisers',
        'creator_shopping_info',
        'profile_reels_sorting_eligibility',
        'short_drama_role',
        'highlights_tray_type',
        'has_eligible_shop_for_business_growth',
        'is_eligible_for_lead_center',
        'has_opt_eligible_shop',
    )
    for k in KEYS:
        v = nuf.get(k)
        if v is None and raw_user:
            v = raw_user.get(k)
        if v not in (None, '', [], {}, False, 0):
            out[k] = v
    return out


def _friendship_grid(arts) -> dict:
    """Phase 28 baseline /info/ chaining_suggestions (= chaining_results) icindeki
    her user icin viewer<->X friendship_status TAM dolu dict. Bu cluster
    sample'larinda bos donen veri."""
    raw_user = _load_baseline_user(arts)
    if not raw_user:
        return {'rows': [], 'note': 'phase28_baseline_info.raw.json yok'}

    chain = (raw_user.get('chaining_suggestions')
              or raw_user.get('chaining_results') or [])
    rows = []
    for u in chain:
        fs = u.get('friendship_status') or {}
        rows.append({
            'pk': str(u.get('pk') or ''),
            'username': u.get('username'),
            'full_name': u.get('full_name'),
            'is_private': u.get('is_private'),
            'is_verified': u.get('is_verified'),
            'profile_pic_id': u.get('profile_pic_id'),
                                          
            'fs_following': fs.get('following'),
            'fs_followed_by': fs.get('followed_by'),
            'fs_is_bestie': fs.get('is_bestie'),
            'fs_is_feed_favorite': fs.get('is_feed_favorite'),
            'fs_is_restricted': fs.get('is_restricted'),
            'fs_incoming_request': fs.get('incoming_request'),
            'fs_outgoing_request': fs.get('outgoing_request'),
            'fs_muting': fs.get('muting'),
            'fs_blocking': fs.get('blocking'),
            'fs_is_eligible_to_subscribe':
                fs.get('is_eligible_to_subscribe'),
            'fs_subscribed': fs.get('subscribed'),
        })

                        
    counts = {
        'total': len(rows),
        'fs_following': sum(1 for r in rows if r['fs_following']),
        'fs_followed_by': sum(1 for r in rows if r['fs_followed_by']),
        'fs_is_bestie': sum(1 for r in rows if r['fs_is_bestie']),
        'fs_subscribed': sum(1 for r in rows if r['fs_subscribed']),
        'fs_is_feed_favorite': sum(1 for r in rows if r['fs_is_feed_favorite']),
        'fs_blocking': sum(1 for r in rows if r['fs_blocking']),
        'fs_is_restricted': sum(1 for r in rows if r['fs_is_restricted']),
        'fs_incoming_request': sum(1 for r in rows if r['fs_incoming_request']),
        'fs_outgoing_request': sum(1 for r in rows if r['fs_outgoing_request']),
        'is_private_count': sum(1 for r in rows if r['is_private']),
        'is_verified_count': sum(1 for r in rows if r['is_verified']),
    }
    return {'rows': rows, 'counts': counts}


def _leaked_counts(arts) -> dict:
    """API'den sizdirilan kantitatif sayilar: f_graphql gql_total_count,
    usertags_count, follower/following/media count cross-source."""
    out = {}
    pb_path = arts.target_dir + '/private_bypass.json'
    import os, json as _json
    if os.path.exists(pb_path):
        try:
            with open(pb_path, encoding='utf-8') as f:
                pb = _json.load(f)
            f_gql = pb.get('f_graphql') or {}
            if f_gql.get('gql_total_count'):
                out['gql_followers_total'] = f_gql['gql_total_count']
        except (OSError, _json.JSONDecodeError):
            pass

    pi = arts.get('presence_intel') or {}
    nuf = _safe_get(pi, 'non_ui_fields', 'found_fields') or {}
    raw_user = _load_baseline_user(arts)

    for k in ('follower_count', 'following_count', 'media_count',
              'usertags_count', 'total_clips_count', 'total_igtv_videos',
              'mutual_followers_count', 'mutual_friends_count',
              'total_ar_effects'):
        v = (raw_user or {}).get(k) if raw_user else None
        if v is None:
            v = nuf.get(k)
        if v not in (None, ''):
            out[k] = v

                                   
    cp_path = arts.target_dir + '/cross_platform_bypass.json'
    if os.path.exists(cp_path):
        try:
            with open(cp_path, encoding='utf-8') as f:
                cp = _json.load(f)
            tu = (cp.get('th_user_info') or {}).get('threads_user') or {}
            if tu:
                out['threads_follower_count'] = tu.get('follower_count')
                out['threads_following_count'] = tu.get('following_count')
                out['threads_media_count'] = tu.get('media_count')
        except (OSError, _json.JSONDecodeError):
            pass

    return out


def _load_baseline_user(arts):
    """phase28_baseline_info.raw.json icindeki user objesini cache'le yukle."""
    import os, json as _json
    path = os.path.join(arts.target_dir, 'phase28_baseline_info.raw.json')
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as f:
            d = _json.load(f)
        return d.get('user') or {}
    except (OSError, _json.JSONDecodeError):
        return None


                                                                             
                                                                       
                                                                             

def build_activity_timeline(arts: Artifacts) -> dict:
    """Phase 29 likes + comments → kronolojik timeline.

    Bu target'in CLUSTER icine yaptigi etkilesimler (target -> X yonu).
    Timeline'da her item: kind, ts, owner_username, owner_pk, caption/text,
    media_url, comment_pk vb.
    """
    arch = arts.get('archeology_p29') or {}
    likes = arch.get('likes') or []
    comments = arch.get('comments') or []
    if not (likes or comments):
        return {
            'present': False,
            'total_likes': 0, 'total_comments': 0,
            'first_iso': None, 'last_iso': None, 'span_days': None,
            'top_owners': [], 'timeline': [],
        }

    events = []
    for l in likes:
        events.append({
            'kind': 'like',
            'ts': l.get('media_taken_at_ts') or 0,
            'iso': l.get('media_taken_at_iso'),
            'media_id': l.get('media_id'),
            'media_url': l.get('media_url'),
            'media_code': l.get('media_code'),
            'owner_pk': l.get('media_owner_pk'),
            'owner_username': l.get('media_owner_username'),
            'caption_head': l.get('media_caption_head'),
        })
    for c in comments:
        events.append({
            'kind': 'comment',
            'ts': c.get('comment_ts') or c.get('media_taken_at_ts') or 0,
            'iso': c.get('comment_iso')
                or c.get('media_taken_at_iso'),
            'media_id': c.get('media_id'),
            'media_url': c.get('media_url'),
            'media_code': c.get('media_code'),
            'owner_pk': c.get('media_owner_pk'),
            'owner_username': c.get('media_owner_username'),
            'comment_text': c.get('comment_text'),
            'comment_pk': c.get('comment_pk'),
            'comment_like_count': c.get('comment_like_count'),
        })
    events.sort(key=lambda e: -(e.get('ts') or 0))                 

    return {
        'present': True,
        'total_likes': arch.get('total_likes') or len(likes),
        'total_comments': arch.get('total_comments') or len(comments),
        'first_iso': arch.get('first_interaction_iso'),
        'last_iso': arch.get('last_interaction_iso'),
        'span_days': arch.get('interaction_span_days'),
        'top_owners': arch.get('top_interacted_owners') or [],
        'cluster_size': arch.get('cluster_size'),
        'accounts_attempted': arch.get('accounts_attempted'),
        'timeline': events,
    }
