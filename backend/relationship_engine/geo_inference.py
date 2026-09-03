"""Target lokasyon cikarimi — coklu sinyal birlesimi.

CDN edge code (scontent-ist1, scontent-fra3 vb.) VIEWER-side, target lokasyonu
icin guvenilmez. Bu modul **target-spesifik** sinyalleri toplar:

  1) **Timezone inference** — target'in aktivite timestamp'lerini saat
     histogram'ina cevir, "uyku saatleri" (en dusuk aktivite 6 saat) ve
     "pik saatler" (yuksek aktivite) → timezone tahmini.
     Kaynaklar: Phase 26 inbox (last_permanent_item_ts, last_activity_at,
     last_seen_at_per_user), Phase 26 rest_presence (last_activity_at_ms),
     Phase 26 story_timing (latest_reel_media), Phase 29 archeology likes/
     comments timestamps, Phase 31 news_inbox event timestamps.

  2) **Tagged location centroid** — target'in tagged_feed.cluster_pivot'ta
     gectigi postlardaki location.lat/lng → fiziksel co-occurence yerleri.
     En sik gecen sehir = muhtemel ev/is yeri.

  3) **Bio text city/country scan** — bilinen Turkiye sehirleri + uluslararasi
     sehir/ulke kelimeleri biography uzerinde regex.

  4) **Cluster country distribution** — chaining_cluster.json (Phase 26
     extended bearer 80 user) icindeki is_in_eu/is_in_canada flag dagilimi
     (eger dolu ise). Yakin halkadaki kisilerin ulke bilgisi target'in
     ulkesi icin guclu prior.

  5) **Cluster language distribution** — hedefe ait chaining/discover
     kumesindeki adlarda Turkceye ozgu karakterlerin toplu orani. Tek bir
     kullanici adi degil, yeterli buyuklukteki hedef-spesifik sosyal kume
     uzerinden zayif/orta kuvvette ulke sinyali uretir.

  6) **Avatar upload saat dagilimi** — cluster uyelerinin avatar upload
     saatlerini sadece timezone-destekleyici tani olarak tutar. Avatar degistirme
     saati hedef aktivitesi degildir ve tek basina ulke oyu URETMEZ.

Cikti formati:
  {
    'timezone_inference': {
       'sample_count': int,
       'hour_histogram_utc': dict[hour:str, count],
       'low_activity_window_utc': [start_h, end_h],
       'high_activity_window_utc': [start_h, end_h],
       'estimated_local_timezone': 'UTC+3' (string),
       'estimated_country_hints': ['Turkey/Greece/...']
    },
    'tagged_locations': {
       'distinct_count': int,
       'top_locations': [{name, city, lat, lng, count}],
       'centroid_lat': float, 'centroid_lng': float,
    },
    'bio_text_matches': [
       {'pattern': 'turkish_city_istanbul', 'match': 'İstanbul', 'context': '...'}
    ],
    'cluster_country_distribution': {
       'is_in_eu_true_count': int,
       'is_in_canada_true_count': int,
       'sample_size': int,
    },
    'avatar_upload_hour_histogram': dict[hour:str, count],
    'final_inference': {
       'best_country_guess': str,
       'best_timezone_guess': str,
       'confidence': 'low'/'medium'/'high',
       'reasoning': [list of strings]
    }
  }
"""

import datetime
import re

from .loader import Artifacts


                                                                       
_TURK_CITIES = [
    'istanbul', 'ankara', 'izmir', 'bursa', 'adana', 'gaziantep', 'konya',
    'antalya', 'kayseri', 'mersin', 'eskisehir', 'eskişehir', 'diyarbakir',
    'diyarbakır', 'samsun', 'denizli', 'sanliurfa', 'şanlıurfa', 'malatya',
    'kahramanmaras', 'kahramanmaraş', 'erzurum', 'van', 'batman', 'elazig',
    'elazığ', 'sakarya', 'kocaeli', 'tekirdag', 'tekirdağ', 'manisa',
    'trabzon', 'mugla', 'muğla', 'aydin', 'aydın', 'balikesir', 'balıkesir',
    'hatay', 'kütahya', 'kutahya', 'edirne', 'kirklareli', 'kırklareli',
    'rize', 'ordu', 'giresun', 'sinop', 'kastamonu', 'corum', 'çorum',
    'amasya', 'tokat', 'sivas', 'yozgat', 'kirsehir', 'kırşehir', 'aksaray',
    'nigde', 'niğde', 'nevsehir', 'nevşehir', 'karaman', 'burdur', 'isparta',
    'usak', 'uşak', 'afyonkarahisar', 'afyon', 'duzce', 'düzce', 'bolu',
    'zonguldak', 'bartin', 'bartın', 'karabuk', 'karabük',
    'bayburt', 'gumushane', 'gümüşhane', 'agri', 'ağrı', 'ardahan', 'igdir',
    'iğdır', 'kars', 'erzincan', 'tunceli', 'bingol', 'bingöl', 'mus',
    'muş', 'bitlis', 'siirt', 'sirnak', 'şırnak', 'mardin', 'hakkari',
    'osmaniye', 'kilis', 'cankiri', 'çankırı', 'canakkale', 'çanakkale',
    'bilecik', 'yalova',
]

_TURKEY_HINTS = [
    'turkey', 'türkiye', 'turkiye', '🇹🇷',
]

                                                                            
                                                                              
                          
_TURKISH_STRONG_CHARS_RE = re.compile(r'[ğĞıİşŞ]')
_TURKISH_SUPPORT_CHARS_RE = re.compile(r'[çÇöÖüÜ]')

_COUNTRY_HINTS = {
    'turkey':       ['turkey', 'türkiye', 'turkiye', '🇹🇷'],
    'germany':      ['germany', 'deutschland', '🇩🇪'],
    'usa':          ['usa', 'united states', 'america', '🇺🇸'],
    'uk':           ['united kingdom', 'england', 'london', '🇬🇧'],
    'france':       ['france', 'paris', '🇫🇷'],
    'italy':        ['italy', 'italia', 'roma', '🇮🇹'],
    'spain':        ['spain', 'españa', 'madrid', '🇪🇸'],
    'netherlands':  ['netherlands', 'amsterdam', '🇳🇱'],
    'greece':       ['greece', 'athens', '🇬🇷'],
    'russia':       ['russia', 'moscow', 'россия', '🇷🇺'],
    'ukraine':      ['ukraine', 'kyiv', '🇺🇦'],
    'azerbaijan':   ['azerbaijan', 'baku', '🇦🇿'],
    'iran':         ['iran', 'tehran', '🇮🇷'],
    'saudi':        ['saudi', 'riyadh', '🇸🇦'],
    'uae':          ['dubai', 'abu dhabi', 'uae', '🇦🇪'],
    'india':        ['india', 'mumbai', 'delhi', '🇮🇳'],
}

                                                            
_TZ_TO_COUNTRIES = {
    'UTC+3':  ['Turkey', 'Saudi Arabia', 'Russia (Moscow)', 'East Africa'],
    'UTC+2':  ['Greece', 'Egypt', 'Israel', 'South Africa', 'Eastern EU'],
    'UTC+1':  ['Germany', 'France', 'Italy', 'Spain', 'Central EU'],
    'UTC+0':  ['UK', 'Portugal', 'Iceland', 'West Africa'],
    'UTC-3':  ['Argentina', 'Brazil (BR)', 'Suriname'],
    'UTC-5':  ['US East', 'Canada East', 'Colombia', 'Peru'],
    'UTC-8':  ['US Pacific', 'Canada West'],
    'UTC+5':  ['Pakistan', 'Maldives'],
    'UTC+5:30': ['India', 'Sri Lanka'],
    'UTC+8':  ['China', 'Singapore', 'Philippines', 'Australia (Perth)'],
    'UTC+9':  ['Japan', 'Korea'],
    'UTC+10': ['Australia East'],
}


def _collect_target_timestamps(arts: Artifacts) -> list[int]:
    """Target'in aktivite timestamp'lerini topla (epoch seconds)."""
    ts_list = []
    pi = arts.get('presence_intel') or {}
    arch = arts.get('archeology_p29') or {}
    ni = arts.get('news_inbox') or {}

                                                
    rest = pi.get('rest_presence') or {}
    for label, e in rest.items():
        if not isinstance(e, dict):
            continue
        tp = e.get('target_presence') or {}
        if tp.get('last_activity_at_ms'):
            try:
                ts_list.append(int(float(tp['last_activity_at_ms']) / 1000))
            except (TypeError, ValueError):
                pass

                                                          
    inbox = pi.get('inbox') or {}
    for label, e in inbox.items():
        if not isinstance(e, dict):
            continue
        for key, unit_div in (
                ('last_permanent_item_ts', 1_000_000),
                ('last_activity_at', 1_000_000)):
            v = e.get(key)
            if v:
                try:
                    ts_list.append(int(float(v) / unit_div))
                except (TypeError, ValueError):
                    pass
                                                     
        for pk, info in (e.get('last_seen_at_per_user') or {}).items():
            v = info.get('ts') if isinstance(info, dict) else None
            if v:
                try:
                    ts_list.append(int(float(v) / 1_000_000))
                except (TypeError, ValueError):
                    pass

                                             
    st = pi.get('story_timing') or {}
    for label, e in st.items():
        if not isinstance(e, dict):
            continue
        for key in ('latest_reel_media', 'newest_item_ts',
                     'first_hl_latest_reel_media'):
            v = e.get(key)
            if v:
                try:
                    ts_list.append(int(float(v)))
                except (TypeError, ValueError):
                    pass

                                                                        
    for like in (arch.get('likes') or []):
        ts = like.get('media_taken_at_ts')
        if ts:
            try: ts_list.append(int(ts))
            except (TypeError, ValueError): pass
    for c in (arch.get('comments') or []):
        ts = c.get('comment_ts') or c.get('media_taken_at_ts')
        if ts:
            try: ts_list.append(int(ts))
            except (TypeError, ValueError): pass

                                                                          
    for ev in (ni.get('target_events') or []):
        ts = ev.get('timestamp')
        if ts:
            try: ts_list.append(int(ts))
            except (TypeError, ValueError): pass

    return [t for t in ts_list if t > 1000000000]                      


def _hour_histogram(ts_list: list[int]) -> dict:
    h = {i: 0 for i in range(24)}
    for ts in ts_list:
        try:
            hour = datetime.datetime.fromtimestamp(
                ts, tz=datetime.timezone.utc).hour
            h[hour] += 1
        except (OSError, ValueError, OverflowError):
            continue
    return h


def _find_low_activity_window(hist: dict, window_size: int = 6) -> tuple:
    """En dusuk toplam aktivite gosteren window_size saatlik pencere
    (uyku saatleri). 0-23 cyclic."""
    total_per_window = []
    for start in range(24):
        s = sum(hist[(start + i) % 24] for i in range(window_size))
        total_per_window.append((s, start))
    total_per_window.sort()
    best_start = total_per_window[0][1]
    return (best_start, (best_start + window_size - 1) % 24)


def _estimate_timezone_from_sleep(sleep_window: tuple) -> str | None:
    """Insanlar genelde local 23:00-07:00 arasi uyur (UTC ofset 0 ise sleep
    UTC 23-07). Bu pencerenin merkezi local 03:00 kabul edilirse:
       sleep_center_utc = (start_h + (window_size-1)/2) % 24
       local_3 - utc_sleep_center = utc_offset
       → utc_offset = (3 - sleep_center_utc) mod 24
    """
    start, end = sleep_window
                                       
    if end >= start:
        center = (start + end) / 2
    else:
        center = ((start + end + 24) / 2) % 24
                                                           
    offset = round((3 - center) % 24)
    if offset > 12:
        offset -= 24
    sign = '+' if offset >= 0 else '-'
    return f'UTC{sign}{abs(offset)}'


def infer_timezone(arts: Artifacts) -> dict:
    ts_list = _collect_target_timestamps(arts)
    if not ts_list:
        return {
            'sample_count': 0,
            'hour_histogram_utc': {str(i): 0 for i in range(24)},
            'low_activity_window_utc': None,
            'high_activity_window_utc': None,
            'estimated_local_timezone': None,
            'estimated_country_hints': [],
            'note': ('Yeterli timestamp yok. Phase 26 (presence/inbox), Phase 29'
                     ' (archeology), Phase 31 (news_inbox) calistir.'),
        }
    hist = _hour_histogram(ts_list)
    sleep = _find_low_activity_window(hist, window_size=6)
    high = _find_low_activity_window(
        {h: -v for h, v in hist.items()}, window_size=6)                  
    tz = _estimate_timezone_from_sleep(sleep)
    countries = _TZ_TO_COUNTRIES.get(tz, [])
    return {
        'sample_count': len(ts_list),
        'hour_histogram_utc': {str(h): hist[h] for h in range(24)},
        'low_activity_window_utc': list(sleep),
        'high_activity_window_utc': list(high),
        'estimated_local_timezone': tz,
        'estimated_country_hints': countries,
        'note': ('low_activity_window = uyku saatleri (UTC). Local ~03:00 '
                 'merkezli kabul edilir → UTC offset turetilir.'),
    }


def collect_tagged_locations(arts: Artifacts) -> dict:
    """tagged_feed.cluster_pivot.tags_found ve direct.items icindeki
    location.lat/lng'leri topla. Centroid hesapla."""
    tf = arts.get('tagged_feed') or {}
    locs = []

    sources = [
        (tf.get('direct') or {}).get('items') or [],
        (tf.get('cluster_pivot') or {}).get('tags_found') or [],
    ]
    for src in sources:
        for item in src:
            loc = item.get('location') or {}
            if loc.get('lat') and loc.get('lng'):
                locs.append({
                    'pk': loc.get('pk'),
                    'name': loc.get('name'),
                    'city': loc.get('city'),
                    'lat': float(loc['lat']),
                    'lng': float(loc['lng']),
                })

                                                                         
    ts_data = arts.get('tag_search_cluster') or {}
    for post in (ts_data.get('tagged_posts_found') or []):
        n = post.get('location')
        if n and isinstance(n, str):
            locs.append({'name': n, 'lat': None, 'lng': None})

                                  
    by_key = {}
    for loc in locs:
        key = str(loc.get('pk') or 'name:' + (loc.get('name') or ''))
        if key not in by_key:
            by_key[key] = {'pk': loc.get('pk'), 'name': loc.get('name'),
                            'city': loc.get('city'),
                            'lat': loc.get('lat'), 'lng': loc.get('lng'),
                            'count': 0}
        by_key[key]['count'] += 1

    top = sorted(by_key.values(), key=lambda x: -x['count'])

                                  
    pts = [(l['lat'], l['lng']) for l in top
           if l.get('lat') is not None and l.get('lng') is not None]
    centroid = None
    if pts:
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        centroid = {'lat': round(cx, 5), 'lng': round(cy, 5),
                     'point_count': len(pts)}

    return {
        'distinct_count': len(by_key),
        'top_locations': top[:15],
        'centroid': centroid,
    }


def scan_bio_text(arts: Artifacts) -> dict:
    """Target biography uzerinde sehir/ulke regex tarama."""
    ti = arts.get('target_internal') or {}
    pi = arts.get('presence_intel') or {}
    bio = ((ti.get('html_ssr') or {}).get('biography') or '')
    if not bio:
        bio = ((ti.get('info_business_contact') or {}).get('biography') or '')
    if not bio:
                                         
        nuf = (pi.get('non_ui_fields') or {}).get('found_fields') or {}
        bio = nuf.get('biography') or ''
    if not bio:
        return {'biography_present': False, 'matches': []}

    bio_low = bio.lower()
    matches = []
    for city in _TURK_CITIES:
        if re.search(r'\b' + re.escape(city) + r'\b', bio_low):
            matches.append({'pattern': 'turkish_city',
                             'value': city.title(),
                             'country_hint': 'Turkey'})
    for country, kws in _COUNTRY_HINTS.items():
        for kw in kws:
            kw_low = kw.lower()
            if kw_low in bio_low:
                matches.append({'pattern': 'country_keyword',
                                 'value': kw,
                                 'country_hint': country.title()})
             
    seen = set()
    uniq = []
    for m in matches:
        k = (m['pattern'], m['value'].lower())
        if k in seen:
            continue
        seen.add(k)
        uniq.append(m)
    return {
        'biography_present': True,
        'biography_head': bio[:300],
        'matches': uniq,
    }


def cluster_country_distribution(arts: Artifacts) -> dict:
    """chaining_cluster.json (Phase 26 80 user) sample'larinda is_in_eu/
    is_in_canada flag dagilimi. Bu flag'lar genelde dolu degil ama kontrol
    ediyoruz."""
    cc = arts.get('chaining_cluster') or {}
    users = cc.get('users') or []
    eu_true = sum(1 for u in users if u.get('is_in_eu') is True)
    eu_false = sum(1 for u in users if u.get('is_in_eu') is False)
    canada_true = sum(1 for u in users if u.get('is_in_canada') is True)
    return {
        'sample_size': len(users),
        'is_in_eu_true_count': eu_true,
        'is_in_eu_false_count': eu_false,
        'is_in_canada_true_count': canada_true,
        'note': ('Phase 26 chaining_cluster sample'
                 'larinda flag genelde dolu degil; cogunlukla 0 doner.')
    }


def cluster_language_distribution(arts: Artifacts) -> dict:
    """Hedef-spesifik chaining/discover kumesinde Turkce karakter yogunlugu.

    Tek bir isim ulke gostergesi sayilmaz. En az 10 benzersiz hesap, en az
    3 kuvvetli Turkce-karakter hesabi ve toplamda en az %20 destek gerekir.
    Bu sinyal diaspora nedeniyle kesin konum degil, en fazla orta guvenli bir
    "Turkish-speaking network" gostergesidir.
    """
    texts_by_pk: dict[str, list[str]] = {}
    for artifact_name in ('chaining_cluster', 'discover_p32'):
        payload = arts.get(artifact_name) or {}
        for user in (payload.get('users') or []):
            pk = user.get('pk')
            if not pk:
                continue
            parts = [str(user.get(key) or '')
                     for key in ('username', 'full_name', 'social_context')]
            text = ' '.join(part for part in parts if part)
            if text:
                texts_by_pk.setdefault(str(pk), []).append(text)

    sample_size = len(texts_by_pk)
    strong_count = 0
    support_only_count = 0
    for texts in texts_by_pk.values():
        text = ' '.join(texts)
        if _TURKISH_STRONG_CHARS_RE.search(text):
            strong_count += 1
        elif _TURKISH_SUPPORT_CHARS_RE.search(text):
            support_only_count += 1

    combined_count = strong_count + support_only_count
    strong_ratio = strong_count / sample_size if sample_size else 0.0
    combined_ratio = combined_count / sample_size if sample_size else 0.0
    minimum_strong = max(3, (sample_size + 9) // 10)                
    turkish_network = (
        sample_size >= 10
        and strong_count >= minimum_strong
        and combined_ratio >= 0.20
    )

                                                                           
                                                                              
    vote_weight = 0.0
    if turkish_network:
        vote_weight = 1.2 if (
            combined_ratio >= 0.40 and strong_ratio >= 0.15
        ) else 0.9

    return {
        'sample_size': sample_size,
        'turkish_strong_char_accounts': strong_count,
        'turkish_support_char_accounts': support_only_count,
        'turkish_combined_accounts': combined_count,
        'strong_ratio': round(strong_ratio, 4),
        'combined_ratio': round(combined_ratio, 4),
        'turkish_speaking_network': turkish_network,
        'country_hint': 'Turkey' if turkish_network else None,
        'country_vote_weight': vote_weight,
        'note': ('Toplu dil sinyalidir; diaspora nedeniyle kesin ikamet ulkesi '
                 'olarak yorumlanmaz.'),
    }


def avatar_upload_histogram(arts: Artifacts) -> dict:
    """Cluster uyelerinin profile_pic_id Snowflake decode timestamp'lerinden
    saat histogram'i. Ortak peak saat → ortak timezone (cluster TR ise target
    da TR olasiligi yuksek)."""
    cluster_users = []
    cc = arts.get('chaining_cluster') or {}
    cluster_users.extend(cc.get('users') or [])
    p32 = arts.get('discover_p32') or {}
    cluster_users.extend(p32.get('users') or [])

    _IG_EPOCH_MS = 1314220021721
    hist = {h: 0 for h in range(24)}
    decoded = 0
    for u in cluster_users:
        ppi = u.get('profile_pic_id')
        if not ppi or '_' not in str(ppi):
            continue
        try:
            media_part = str(ppi).split('_', 1)[0]
            media_id = int(media_part)
            ts_ms = (media_id >> 23) + _IG_EPOCH_MS
            hour = datetime.datetime.fromtimestamp(
                ts_ms / 1000, tz=datetime.timezone.utc).hour
            hist[hour] += 1
            decoded += 1
        except (ValueError, TypeError, OSError, OverflowError):
            continue

                    
    peak = _find_low_activity_window(
        {h: -v for h, v in hist.items()}, window_size=6)

    return {
        'cluster_size': len(cluster_users),
        'decoded_count': decoded,
        'hour_histogram_utc': {str(h): hist[h] for h in range(24)},
        'peak_window_utc': list(peak),
        'note': ('Cluster uyelerinin avatar upload saatleri (UTC). Ortak peak'
                 'in target ile cakismasi muhtemel — ayni timezone halkasi.'),
    }


def build_geo_inference(arts: Artifacts) -> dict:
    tz = infer_timezone(arts)
    locs = collect_tagged_locations(arts)
    bio = scan_bio_text(arts)
    cdist = cluster_country_distribution(arts)
    ldist = cluster_language_distribution(arts)
    upload_hist = avatar_upload_histogram(arts)

                                    
    candidates = {}
    reasoning = []

    if tz.get('estimated_country_hints'):
        for c in tz['estimated_country_hints']:
            candidates[c] = candidates.get(c, 0) + 0.4
        reasoning.append(
            f'timezone inference {tz["estimated_local_timezone"]} → '
            f'{", ".join(tz["estimated_country_hints"])} (weight 0.4 each)')

    if bio.get('matches'):
        for m in bio['matches']:
            ch = m.get('country_hint')
            if ch:
                candidates[ch] = candidates.get(ch, 0) + 0.6
        reasoning.append(
            f'bio text matches {len(bio["matches"])} city/country '
            f'(weight 0.6 each)')

    if locs.get('top_locations'):
                           
        cities = {}
        for l in locs['top_locations']:
            c = l.get('city')
            if c:
                cities[c] = cities.get(c, 0) + l.get('count', 1)
        if cities:
            top_city = max(cities.items(), key=lambda x: x[1])
            reasoning.append(
                f'tagged top city: {top_city[0]} (x{top_city[1]})')
                                           
            if any(top_city[0].lower() == c.lower() for c in _TURK_CITIES):
                candidates['Turkey'] = candidates.get('Turkey', 0) + 1.0
                reasoning.append(
                    f'tagged top city is Turkish → +1.0 Turkey')

    if cdist.get('is_in_eu_true_count', 0) > 0:
        n = cdist['is_in_eu_true_count']
        candidates['EU'] = candidates.get('EU', 0) + 0.3 * n
        reasoning.append(
            f'cluster is_in_eu=True count {n} → +0.3 each EU')
    if cdist.get('is_in_canada_true_count', 0) > 0:
        candidates['Canada'] = candidates.get('Canada', 0) + 0.5
        reasoning.append('cluster is_in_canada=True → +0.5 Canada')

    if ldist.get('turkish_speaking_network'):
        weight = float(ldist.get('country_vote_weight') or 0)
        candidates['Turkey'] = candidates.get('Turkey', 0) + weight
        reasoning.append(
            'cluster Turkish-language signal: '
            f'{ldist["turkish_combined_accounts"]}/{ldist["sample_size"]} '
            'accounts, '
            f'{ldist["turkish_strong_char_accounts"]} strong → '
            f'+{weight:.1f} Turkey')

                                                                           
                                                                               
                                                                            
                  
                                           
                                                          
                                         
                                             
                                     
    if upload_hist.get('decoded_count', 0) >= 20:
        hist = upload_hist.get('hour_histogram_utc') or {}
        if hist:
            mode_hour = max(range(24),
                             key=lambda h: hist.get(str(h), 0))
            mode_count = hist.get(str(mode_hour), 0)
            HYPOTHESES = [(22, 0.5), (21, 0.3), (20, 0.2), (19, 0.1)]
            tz_votes = {}
            for local_peak, w in HYPOTHESES:
                offset = round((local_peak - mode_hour) % 24)
                if offset > 12:
                    offset -= 24
                sign = '+' if offset >= 0 else '-'
                avatar_tz = f'UTC{sign}{abs(offset)}'
                tz_votes[avatar_tz] = tz_votes.get(avatar_tz, 0) + w
            reasoning.append(
                f'cluster avatar mode UTC={mode_hour} (n={mode_count}/'
                f'{upload_hist["decoded_count"]}) → '
                f'tz diagnostics: {tz_votes}; country vote disabled '
                f'(weak/non-target signal)')

    best_country = None
    best_score = 0
    if candidates:
        sorted_cands = sorted(candidates.items(), key=lambda x: -x[1])
        best_country, best_score = sorted_cands[0]

    confidence = ('high' if best_score >= 1.5 else
                   'medium' if best_score >= 0.7 else
                   'low' if best_score > 0 else 'none')

    return {
        'timezone_inference': tz,
        'tagged_locations': locs,
        'bio_text_matches': bio,
        'cluster_country_distribution': cdist,
        'cluster_language_distribution': ldist,
        'avatar_upload_histogram': upload_hist,
        'final_inference': {
            'best_country_guess': best_country,
            'best_score': round(best_score, 2),
            'confidence': confidence,
            'all_candidates': dict(sorted(candidates.items(),
                                            key=lambda x: -x[1])),
            'reasoning': reasoning,
        },
    }
