"""Yerel Instagram OSINT uygulamasinin HTTP/API sunucusu.

Frontend'i ``../frontend`` altindan servis eder; veri toplama ve relationship
engine tamamen ``backend`` icinde calisir. Sunucu yalnizca localhost kullanimi
icin tasarlanmistir.
"""

import argparse
import contextlib
import hashlib
import ipaddress
import io
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .relationship_engine import cli as engine_cli
from .relationship_engine.config import (DEFAULT_ARTIFACT_ROOT, OUTPUT_SUBDIR,
                                           ARTIFACT_FILES)
from .relationship_engine.loader import TargetScopeConflict


                             
PHASE_FLAGS = ['presence', 'dsa', 'inflate', 'archeology', 'tagged',
                'news', 'chain', 'internal', 'followgraph', 'reciprocal',
                'banyan']

USERNAME_RE = re.compile(r'^[A-Za-z0-9._]{1,30}$')
PK_RE = re.compile(r'^\d{1,30}$')
AVATAR_HOST_SUFFIXES = ('cdninstagram.com', 'fbcdn.net')
AVATAR_MAX_BYTES = 5 * 1024 * 1024
AVATAR_PROFILE_MAX_BYTES = 3 * 1024 * 1024
AVATAR_PROXY_VERSION = 2
AVATAR_REMOTE_LIMIT = threading.BoundedSemaphore(3)
AVATAR_LOCKS_GUARD = threading.Lock()
AVATAR_LOCKS = {}
AVATAR_FAILURE_TTL_SECONDS = 300
AVATAR_FAILURES = {}
ANALYSIS_SLOT = threading.Lock()
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
    'X-Frame-Options': 'DENY',
    'Cross-Origin-Resource-Policy': 'same-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
                                                                           
                                                                           
                                         
    'Content-Security-Policy': (
        "default-src 'self'; base-uri 'none'; object-src 'none'; "
        "frame-src 'none'; frame-ancestors 'none'; form-action 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; font-src 'self' data:; "
        "connect-src 'self'; media-src 'none'; worker-src 'none'"
    ),
}
AVATAR_TRANSPARENT_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
    b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00'
    b'\x02\x02D\x01\x00;'
)


HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(HERE)
STATIC_DIR = os.path.join(APP_DIR, 'frontend')
PIPELINE_DIR = HERE


def _valid_username(username: str) -> bool:
    return bool(USERNAME_RE.fullmatch(username or ''))


def _is_loopback_hostname(hostname: str) -> bool:
    """Accept only explicit loopback names/addresses (no DNS aliases)."""
    host = str(hostname or '').strip().lower().rstrip('.')
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _parse_host_header(value: str, expected_port: int):
    """Return normalized ``(host, port)`` for a valid local Host header."""
    raw = str(value or '').strip()
    if (not raw or ',' in raw or '/' in raw or '\\' in raw
            or '?' in raw or '#' in raw):
        return None
    try:
        parsed = urllib.parse.urlsplit('//' + raw)
        host = (parsed.hostname or '').lower().rstrip('.')
        port = parsed.port
    except (TypeError, ValueError):
        return None
    if (parsed.username is not None or parsed.password is not None
            or not _is_loopback_hostname(host)):
        return None
    if port is None:
        if expected_port not in (80, 443):
            return None
        port = expected_port
    if port != expected_port:
        return None
    return host, port


def _valid_host_header(value: str, expected_port: int) -> bool:
    return _parse_host_header(value, expected_port) is not None


def _same_origin_request(handler) -> bool:
    """Reject browser cross-site requests to state-changing local routes."""
    fetch_site = str(handler.headers.get('Sec-Fetch-Site') or '').lower()
    if fetch_site and fetch_site not in ('same-origin', 'none'):
        return False

    origin = str(handler.headers.get('Origin') or '').strip()
    if not origin:
                                                                               
        return True
    if origin.lower() == 'null':
        return False

    expected_port = int(handler.server.server_address[1])
    host_info = _parse_host_header(handler.headers.get('Host'), expected_port)
    if host_info is None:
        return False
    try:
        parsed = urllib.parse.urlsplit(origin)
        origin_host = (parsed.hostname or '').lower().rstrip('.')
        origin_port = parsed.port or (80 if parsed.scheme == 'http' else 443)
    except (TypeError, ValueError):
        return False
    return (parsed.scheme == 'http'
            and not parsed.username and not parsed.password
            and parsed.path in ('', '/')
            and not parsed.query and not parsed.fragment
            and origin_host == host_info[0]
            and origin_port == host_info[1])


def _safe_join(base: str, *parts: str) -> str | None:
    """base disina cikan path traversal girislerini reddet."""
    base_abs = os.path.realpath(base)
    candidate = os.path.realpath(os.path.join(base_abs, *parts))
    try:
        if os.path.commonpath((base_abs, candidate)) != base_abs:
            return None
    except ValueError:
        return None
    return candidate


def find_cached_target_pk(artifacts_root: str, username: str) -> str | None:
    """Eski veya yeni artifact'lardan target PK bul."""
    if not _valid_username(username):
        return None
    candidates = (
        (os.path.join(artifacts_root, username, 'critical_intel.json'),
         ('pk', 'user.pk', 'intel.pk')),
        (os.path.join(artifacts_root, username, OUTPUT_SUBDIR,
                      'relationships_ranked.json'), ('target_pk',)),
        (os.path.join(artifacts_root, username,
                      'target_internal_phase33.json'), ('target_pk', 'pk')),
    )

    def nested(obj, dotted):
        cur = obj
        for key in dotted.split('.'):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(key)
        return cur

    for path, keys in candidates:
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        for key in keys:
            value = nested(data, key)
            if value:
                return str(value)
    return None


                                                                             
            
                                                                             

def list_users(artifacts_root: str) -> list[dict]:
    """artifacts/<u>/ altindaki her klasor bir user. Hangileri 'engine
    kosulmus' (relationships/relationships_ranked.json var) onu da soyler."""
    if not os.path.isdir(artifacts_root):
        return []
    out = []
    for name in sorted(os.listdir(artifacts_root)):
        if not _valid_username(name):
            continue
        path = os.path.join(artifacts_root, name)
        if not os.path.isdir(path):
            continue
        rel_json = os.path.join(path, OUTPUT_SUBDIR,
                                  'relationships_ranked.json')
        artifact_count = sum(
            1 for fn in ARTIFACT_FILES.values()
            if os.path.exists(os.path.join(path, fn)))
        out.append({
            'username': name,
            'has_engine_output': os.path.exists(rel_json),
            'engine_mtime': (os.path.getmtime(rel_json)
                              if os.path.exists(rel_json) else None),
            'artifacts_present': artifact_count,
            'artifacts_total': len(ARTIFACT_FILES),
        })
    return out


def load_engine_output(artifacts_root: str, username: str) -> dict | None:
    if not _valid_username(username):
        return None
    path = os.path.join(artifacts_root, username, OUTPUT_SUBDIR,
                         'relationships_ranked.json')
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def load_text_report(artifacts_root: str, username: str) -> str | None:
    if not _valid_username(username):
        return None
    path = os.path.join(artifacts_root, username, OUTPUT_SUBDIR,
                         'relationship_report.txt')
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return f.read()


def _avatar_source_for(artifacts_root: str, username: str,
                       pk: str) -> tuple[str, str] | None:
    """Engine output icinden avatar URL'si ve profil kullanici adini bul.

    URL istemciden alinmaz; boylece avatar endpoint'i genel amacli bir proxyye
    veya SSRF yuzeyine donusmez.
    """
    data = load_engine_output(artifacts_root, username)
    if not data:
        return None

    if str(data.get('target_pk') or '') == str(pk):
        target_intel = data.get('target_intel') or {}
        url = ((target_intel.get('avatar') or {}).get('profile_pic_url')
               or (target_intel.get('profile') or {}).get('profile_pic_url'))
        if url:
            return str(url), str(data.get('username') or username)

    for person in (data.get('people') or []):
        if str(person.get('pk') or '') == str(pk) and person.get('profile_pic_url'):
            profile_username = str(person.get('username') or '')
            if _valid_username(profile_username):
                return str(person['profile_pic_url']), profile_username
    return None


class _OpenGraphImageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.image_url = None

    def handle_starttag(self, tag, attrs):
        if self.image_url or tag.lower() != 'meta':
            return
        values = {str(key).lower(): value for key, value in attrs}
        if str(values.get('property') or '').lower() == 'og:image':
            self.image_url = values.get('content')


def _avatar_cookie_header() -> str:
    """Yerel .env'deki IG oturumunu yalniz instagram.com istegine ekle."""
    env_candidates = (
        os.environ.get('IG_ENV_FILE'),
        os.path.join(APP_DIR, '.env'),
    )
    env_path = next((path for path in env_candidates
                     if path and os.path.isfile(path)), None)
    if not env_path:
        return ''
    values = {}
    try:
        with open(env_path, encoding='utf-8') as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                    value = value[1:-1]
                values[key.strip()] = value
    except OSError:
        return ''
    names = (
        ('sessionid', 'IG_SESSIONID'),
        ('ds_user_id', 'IG_DS_USER_ID'),
        ('csrftoken', 'IG_CSRFTOKEN'),
        ('mid', 'IG_MID'),
        ('ig_did', 'IG_IG_DID'),
        ('datr', 'IG_DATR'),
    )
    return '; '.join(f'{cookie}={values[env_key]}'
                     for cookie, env_key in names if values.get(env_key))


def _avatar_url_expired(url: str) -> bool:
    """Instagram'in hex ``oe`` zaman damgasi gecmisse bosuna 403 deneme."""
    try:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        expires = int((query.get('oe') or [''])[0], 16)
        return expires <= time.time() + 60
    except (TypeError, ValueError, IndexError):
        return False


def _allowed_instagram_page_url(url: str) -> bool:
    """Cookie-bearing refresh requests must remain on Instagram itself."""
    try:
        parsed = urllib.parse.urlparse(url)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    host = (parsed.hostname or '').lower().rstrip('.')
    return (parsed.scheme == 'https'
            and host in ('instagram.com', 'www.instagram.com')
            and port in (None, 443)
            and parsed.username is None and parsed.password is None)


class _RestrictedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow only a small number of redirects accepted by ``validator``."""
    max_redirections = 3
    max_repeats = 2

    def __init__(self, validator):
        super().__init__()
        self._validator = validator

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urljoin(req.full_url, newurl)
        if not self._validator(target):
            raise urllib.error.URLError('redirect target rejected')
        return super().redirect_request(req, fp, code, msg, headers, target)


def _restricted_urlopen(request, validator, timeout: int):
    """Open a trusted URL and validate both every redirect and final URL."""
    if not validator(request.full_url):
        raise urllib.error.URLError('request target rejected')
    opener = urllib.request.build_opener(_RestrictedRedirectHandler(validator))
    response = opener.open(request, timeout=timeout)
    if not validator(response.geturl()):
        response.close()
        raise urllib.error.URLError('final response target rejected')
    return response


def _refresh_avatar_url(profile_username: str) -> str | None:
    """Profil HTML'indeki guncel og:image imzasini al."""
    if not _valid_username(profile_username):
        return None
    page_url = ('https://www.instagram.com/'
                + urllib.parse.quote(profile_username, safe='._') + '/')
    headers = {
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/141.0.0.0 Safari/537.36'),
        'Accept': ('text/html,application/xhtml+xml,application/xml;q=0.9,'
                   'image/avif,image/webp,*/*;q=0.8'),
        'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.7',
        'Referer': 'https://www.instagram.com/',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'Sec-CH-UA': ('"Google Chrome";v="141", "Not?A_Brand";v="8", '
                      '"Chromium";v="141"'),
        'Sec-CH-UA-Mobile': '?0',
        'Sec-CH-UA-Platform': '"Windows"',
    }
    cookie = _avatar_cookie_header()
    if cookie:
        headers['Cookie'] = cookie
    request = urllib.request.Request(page_url, headers=headers)
    try:
        with AVATAR_REMOTE_LIMIT:
            with _restricted_urlopen(
                    request, _allowed_instagram_page_url, timeout=20) as response:
                raw_html = response.read(AVATAR_PROFILE_MAX_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    if not raw_html or len(raw_html) > AVATAR_PROFILE_MAX_BYTES:
        return None
    parser = _OpenGraphImageParser()
    try:
        parser.feed(raw_html.decode('utf-8', errors='replace'))
    except (ValueError, TypeError):
        return None
    refreshed = str(parser.image_url or '')
    return refreshed if _allowed_avatar_url(refreshed) else None


def _avatar_lock(cache_path: str):
    """Ayni avatar People/Graph tarafindan birlikte istenirse tek kez cek."""
    with AVATAR_LOCKS_GUARD:
        return AVATAR_LOCKS.setdefault(cache_path, threading.Lock())


def _read_cached_avatar(cache_path: str):
    try:
        with open(cache_path, 'rb') as cached:
            body = cached.read(AVATAR_MAX_BYTES + 1)
        if (body and len(body) <= AVATAR_MAX_BYTES
                and _image_content_type(body) is not None):
            return body
    except OSError:
        pass
    return None


def _download_avatar(url: str, profile_username: str):
    request = urllib.request.Request(url, headers={
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 Chrome/141 Safari/537.36'),
        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        'Referer': f'https://www.instagram.com/{profile_username}/',
    })
    with AVATAR_REMOTE_LIMIT:
        with _restricted_urlopen(
                request, _allowed_avatar_url, timeout=20) as response:
            body = response.read(AVATAR_MAX_BYTES + 1)
    return body


def _allowed_avatar_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    host = (parsed.hostname or '').lower().rstrip('.')
    return (parsed.scheme == 'https'
            and port in (None, 443)
            and parsed.username is None and parsed.password is None
            and any(host == suffix or host.endswith('.' + suffix)
                    for suffix in AVATAR_HOST_SUFFIXES))


def _image_content_type(body: bytes) -> str | None:
    """Return only browser-safe raster types proven by file signatures."""
    if body.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if body.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if body.startswith(b'RIFF') and body[8:12] == b'WEBP':
        return 'image/webp'
    if body.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif'
    if (len(body) >= 12 and body[4:8] == b'ftyp'
            and (body[8:12] in (b'avif', b'avis')
                 or b'avif' in body[8:32] or b'avis' in body[8:32])):
        return 'image/avif'
    return None


def _image_response(body: bytes):
    content_type = _image_content_type(body)
    if content_type is None:
        return _avatar_placeholder('invalid_cached_image')
    return (200, {
        'Content-Type': content_type,
        'Cache-Control': 'public, max-age=604800, immutable',
        'X-Content-Type-Options': 'nosniff',
    }, body)


def _avatar_placeholder(reason: str):
    """Avatar bulunamazsa 502 spam'i yerine alttaki initials'i gorunur birak."""
    return (200, {
        'Content-Type': 'image/gif',
        'Cache-Control': 'no-store, max-age=0',
        'X-Avatar-Fallback': reason,
        'X-Avatar-Proxy-Version': str(AVATAR_PROXY_VERSION),
        'X-Content-Type-Options': 'nosniff',
    }, AVATAR_TRANSPARENT_GIF)


def load_or_fetch_avatar(artifacts_root: str, username: str,
                         pk: str) -> tuple[int, dict, bytes]:
    """Instagram CDN avatarini ilk istekte indir, target artifact'inda cachele."""
    if not _valid_username(username) or not PK_RE.fullmatch(str(pk or '')):
        return _json(400, {'error': 'invalid_avatar_path'})

    cache_dir = _safe_join(artifacts_root, username, 'avatar_cache')
    if cache_dir is None:
        return _json(403, {'error': 'invalid_cache_path'})

    source = _avatar_source_for(artifacts_root, username, pk)
    if not source:
        return _json(404, {'error': 'avatar_url_yok'})
    url, profile_username = source
    if not _allowed_avatar_url(url):
        return _json(403, {'error': 'avatar_host_reddedildi'})

                                                                             
    cache_key = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
    cache_path = _safe_join(cache_dir, f'{pk}-{cache_key}.img')
    if cache_path is None:
        return _json(403, {'error': 'invalid_cache_path'})

    body = _read_cached_avatar(cache_path)
    if body:
        return _image_response(body)

    with _avatar_lock(cache_path):
                                                                           
        body = _read_cached_avatar(cache_path)
        if body:
            return _image_response(body)
        failure_until = AVATAR_FAILURES.get(cache_path, 0)
        if failure_until > time.time():
            return _avatar_placeholder('temporary_unavailable')
        AVATAR_FAILURES.pop(cache_path, None)

        def avatar_failed(reason: str):
            AVATAR_FAILURES[cache_path] = (
                time.time() + AVATAR_FAILURE_TTL_SECONDS)
            return _avatar_placeholder(reason)

        remote_url = url
        refreshed = False
        if _avatar_url_expired(remote_url):
            remote_url = _refresh_avatar_url(profile_username) or remote_url
            refreshed = remote_url != url
        try:
            body = _download_avatar(remote_url, profile_username)
        except urllib.error.HTTPError as exc:
                                                                           
                                                                          
            if not refreshed and exc.code in (403, 404):
                remote_url = _refresh_avatar_url(profile_username)
                refreshed = bool(remote_url and remote_url != url)
                if refreshed:
                    try:
                        body = _download_avatar(remote_url, profile_username)
                    except (urllib.error.URLError, TimeoutError, OSError) as retry_exc:
                        return avatar_failed('refresh_fetch_failed')
                else:
                    return avatar_failed('url_refresh_failed')
            else:
                return avatar_failed('fetch_failed')
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return avatar_failed('fetch_failed')

        if not body or len(body) > AVATAR_MAX_BYTES:
            return avatar_failed('invalid_size')
        if _image_content_type(body) is None:
            return avatar_failed('not_image')

        os.makedirs(cache_dir, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile('wb', delete=False,
                                             dir=cache_dir, suffix='.tmp') as tmp:
                temp_path = tmp.name
                tmp.write(body)
                                                                             
                                                                       
            os.replace(temp_path, cache_path)
        except OSError:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                                                                      
        AVATAR_FAILURES.pop(cache_path, None)
        return _image_response(body)


def load_artifact(artifacts_root: str, username: str, key: str) -> dict | None:
    if not _valid_username(username):
        return None
    fname = ARTIFACT_FILES.get(key)
    if not fname:
        return None
    path = os.path.join(artifacts_root, username, fname)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def run_engine(artifacts_root: str, username: str,
                drop_algorithmic: bool = False) -> dict:
    """relationship_engine.cli.run() cagir, stdout yakala, sonuc dondur."""
    if not _valid_username(username):
        raise ValueError('gecersiz username')
    user_dir = os.path.join(artifacts_root, username)
    if not os.path.isdir(user_dir):
        raise FileNotFoundError(f'artifact dir yok: {user_dir}')
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = engine_cli.run(username, root=artifacts_root,
                                  subdir=OUTPUT_SUBDIR,
                                  drop_algorithmic=drop_algorithmic)
    public_log = buf.getvalue().replace(
        os.path.abspath(artifacts_root), '<artifacts>')
    return {
        'ok': True,
        'paths': {k: os.path.basename(result[k]) for k in (
            'json', 'csv', 'edges', 'nodes', 'gexf', 'text')
                  if result.get(k)},
        'tier_counts': result.get('tier_counts'),
        'meta_summary': {
            'sources': result['meta'].get('sources', {}),
            'bidirectional': result['meta'].get('bidirectional'),
        },
        'log': public_log,
    }


                                                                             
                 
                                                                             

API_ROUTES = []


def route(pattern: str, method: str = 'GET'):
    """Decorator: API_ROUTES'a (compiled_pattern, method, fn) ekler."""
    def deco(fn):
        API_ROUTES.append((re.compile(f'^{pattern}$'), method, fn))
        return fn
    return deco


def exclusive_analysis(fn):
    """Allow only one collector/scoring job per authenticated IG session."""
    def wrapped(handler, match, qs):
        if not ANALYSIS_SLOT.acquire(blocking=False):
            status, headers, body = _json(409, {
                'ok': False,
                'error': 'analysis_busy',
                'msg': 'another analysis is already running',
            })
            headers['Retry-After'] = '5'
            return status, headers, body
        try:
            return fn(handler, match, qs)
        finally:
            ANALYSIS_SLOT.release()
    return wrapped


def _log_current_exception(context: str):
    print(f'[!] {context}', file=sys.stderr)
    traceback.print_exc(file=sys.stderr)


                                              
_CFG = {
    'artifacts_root': DEFAULT_ARTIFACT_ROOT,
}


@route(r'/api/users')
def h_list_users(handler, match, qs):
    return _json(200, list_users(_CFG['artifacts_root']))


@route(r'/api/users/(?P<u>[^/]+)/data')
def h_get_data(handler, match, qs):
    d = load_engine_output(_CFG['artifacts_root'], match['u'])
    if d is None:
        return _json(404, {'error': 'engine_output_yok',
                            'hint': 'POST /api/users/{u}/run cagir'})
    return _json(200, d)


@route(r'/api/users/(?P<u>[^/]+)/avatar/(?P<pk>\d{1,30})')
def h_get_avatar(handler, match, qs):
    """Profil fotografini CDN'den server-side cekip yerel cache'ten sun."""
    return load_or_fetch_avatar(
        _CFG['artifacts_root'], match['u'], match['pk'])


@route(r'/api/users/(?P<u>[^/]+)/report')
def h_get_report(handler, match, qs):
    t = load_text_report(_CFG['artifacts_root'], match['u'])
    if t is None:
        return _json(404, {'error': 'report_yok'})
    return _text(200, t)


@route(r'/api/users/(?P<u>[^/]+)/artifact/(?P<k>[^/]+)')
def h_get_artifact(handler, match, qs):
    d = load_artifact(_CFG['artifacts_root'], match['u'], match['k'])
    if d is None:
        return _json(404, {'error': 'artifact_yok',
                            'available': list(ARTIFACT_FILES.keys())})
    return _json(200, d)


@route(r'/api/users/(?P<u>[^/]+)/run', method='POST')
@exclusive_analysis
def h_run(handler, match, qs):
    drop = qs.get('drop_algorithmic', ['0'])[0] in ('1', 'true', 'True')
    try:
        out = run_engine(_CFG['artifacts_root'], match['u'],
                          drop_algorithmic=drop)
        return _json(200, out)
    except TargetScopeConflict:
        _log_current_exception('relationship engine target scope conflict')
        return _json(409, {
            'ok': False,
            'error': 'target_scope_conflict',
            'msg': 'artifact target IDs disagree; run a fresh analysis',
        })
    except Exception:
        _log_current_exception('relationship engine request failed')
        return _json(500, {'ok': False, 'error': 'engine_failed',
                            'msg': 'relationship scoring failed'})


@route(r'/api/health')
def h_health(handler, match, qs):
    return _json(200, {'ok': True})


@route(r'/api/phases')
def h_phases(handler, match, qs):
    return _json(200, {'phases': PHASE_FLAGS})


@route(r'/api/query')
@exclusive_analysis
def h_query(handler, match, qs):
    """SSE stream — `python phase26_29.py <username>` koshturur, stdout'i
    canli yayinlar. Bitince relationship_engine'i auto-cagirir."""
    username = (qs.get('username', [''])[0] or '').strip()
    phases_csv = (qs.get('phases', [''])[0] or '').strip()
    chain_multi_raw = (qs.get('chain_multi', ['5'])[0] or '5').strip()
    fast_raw = (qs.get('fast', ['1'])[0] or '1').strip().lower()
    drop_raw = (qs.get('drop_algorithmic', ['0'])[0] or '0').strip().lower()
    fast_mode = fast_raw not in ('0', 'false', 'no')
    drop_algorithmic = drop_raw in ('1', 'true', 'yes')
    try:
        chain_multi = max(1, min(20, int(chain_multi_raw)))
    except ValueError:
        chain_multi = 5
    if not _valid_username(username):
        return _json(400, {'error': 'invalid_username',
                            'msg': 'username 1-30 chars [A-Za-z0-9._]'})

    selected = [p for p in (phases_csv.split(',') if phases_csv else [])
                if p in PHASE_FLAGS]

                                 
    handler.send_response(200)
    handler.send_header('Content-Type', 'text/event-stream; charset=utf-8')
    handler.send_header('Cache-Control', 'no-cache')
    handler.send_header('X-Accel-Buffering', 'no')
    handler.send_header('Connection', 'keep-alive')
    for key, value in SECURITY_HEADERS.items():
        handler.send_header(key, value)
    handler.end_headers()

    def emit(payload, event=None):
        try:
            if event:
                handler.wfile.write(f'event: {event}\n'.encode('utf-8'))
            line = f'data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n'
            handler.wfile.write(line.encode('utf-8'))
            handler.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    cmd = [sys.executable, '-u', os.path.join(PIPELINE_DIR, 'phase26_29.py'),
           username]
    for phase in selected:
        cmd.append(f'--{phase}-only')
    cmd.extend(['--chain-multi', str(chain_multi)])
    if fast_mode:
        cmd.extend(['--mqtt-seconds', '0'])
    if not emit({'username': username, 'phases': selected or PHASE_FLAGS,
                 'chain_multi': chain_multi, 'fast_mode': fast_mode,
                 'drop_algorithmic': drop_algorithmic}, event='start'):
        return None

    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'
    env['IG_OSINT_FAST'] = '1' if fast_mode else '0'

    cached_pk = find_cached_target_pk(_CFG['artifacts_root'], username)
    if cached_pk:
        emit({'line': f'[setup] cached target pk bulundu: {cached_pk}'},
             event='log')
    else:
                                                                         
                                                                       
        emit({'line': '[setup] target pk yok; otomatik on hazirlik basliyor...'},
             event='log')
        pre_cmd = [sys.executable, '-u',
                   os.path.join(PIPELINE_DIR, 'prepare_target.py'), username]
        emit({'line': f'[setup] prepare_target.py {username}'}, event='log')
        try:
            pre = subprocess.Popen(
                pre_cmd, cwd=PIPELINE_DIR, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=1, text=True, encoding='utf-8', errors='replace')
        except OSError:
            _log_current_exception('target preparation process failed to start')
            emit({'error': 'process_start_failed',
                  'msg': 'target preparation could not start'}, event='error')
            return None
        for line in pre.stdout:
            if not emit({'line': line.rstrip()}, event='log'):
                try:
                    pre.kill()
                except OSError:
                    pass
                return None
        pre_rc = pre.wait()
        if pre_rc != 0:
            emit({'line': f'[setup] on hazirlik basarisiz (code={pre_rc})'},
                 event='log')
            emit({'returncode': pre_rc}, event='phase_done')
            emit({'msg': 'target hazirlanamadi; cookie ve username kontrol et'},
                 event='engine_skipped')
            emit({'done': True}, event='done')
            return None
        cached_pk = find_cached_target_pk(_CFG['artifacts_root'], username)
        if cached_pk:
            emit({'line': f'[setup] target hazir: pk={cached_pk}'}, event='log')
        else:
            emit({'line': '[setup] pk dosyaya yazilmadi; online fallback denenecek'},
                 event='log')

    try:
        proc = subprocess.Popen(
            cmd, cwd=PIPELINE_DIR, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=1, text=True, encoding='utf-8', errors='replace')
    except OSError:
        _log_current_exception('collection process failed to start')
        emit({'error': 'process_start_failed',
              'msg': 'analysis process could not start'}, event='error')
        return None

    try:
        for line in proc.stdout:
            if not emit({'line': line.rstrip()}, event='log'):
                                                       
                try:
                    proc.kill()
                except OSError:
                    pass
                return None
    except (BrokenPipeError, ConnectionResetError):
        try:
            proc.kill()
        except OSError:
            pass
        return None

    rc = proc.wait()
    emit({'returncode': rc}, event='phase_done')

                                
    if rc == 0:
        try:
            res = run_engine(_CFG['artifacts_root'], username,
                             drop_algorithmic=drop_algorithmic)
            emit({'tier_counts': res.get('tier_counts'),
                   'paths': res.get('paths')}, event='engine_done')
        except TargetScopeConflict:
            _log_current_exception(
                'target scope conflict after collection')
            emit({'error': 'target_scope_conflict',
                  'msg': 'artifact target IDs disagree; run a fresh analysis'},
                 event='engine_error')
        except Exception:
            _log_current_exception('relationship engine failed after collection')
            emit({'error': 'engine_failed',
                  'msg': 'relationship scoring failed'}, event='engine_error')
    else:
        emit({'msg': f'phase26_29 returncode={rc}; engine SKIP'},
              event='engine_skipped')

    emit({'done': True}, event='done')
    return None


                                                                             
                  
                                                                             

def _json(status, obj) -> tuple[int, dict, bytes]:
    body = json.dumps(obj, ensure_ascii=False, default=str).encode('utf-8')
    return (status, {'Content-Type': 'application/json; charset=utf-8',
                      'Cache-Control': 'no-store'}, body)


def _text(status, txt) -> tuple[int, dict, bytes]:
    body = txt.encode('utf-8')
    return (status, {'Content-Type': 'text/plain; charset=utf-8',
                      'Cache-Control': 'no-store'}, body)


def _file(path: str) -> tuple[int, dict, bytes]:
    if not os.path.isfile(path):
        return _text(404, 'not found')
    ctype, _ = mimetypes.guess_type(path)
    content_type = ctype or 'application/octet-stream'
    if (content_type.startswith('text/')
            or content_type in {
                'application/javascript',
                'application/json',
                'application/manifest+json',
                'application/xml',
                'image/svg+xml',
            }
            or content_type.endswith('+json')
            or content_type.endswith('+xml')):
        content_type = f'{content_type}; charset=utf-8'
    with open(path, 'rb') as f:
        body = f.read()
    return (200, {'Content-Type': content_type,
                   'Cache-Control': 'no-cache'}, body)


                                                                             
                       
                                                                             

class Handler(BaseHTTPRequestHandler):
    server_version = 'RelEngineWebUI/1.0'

    def log_message(self, format, *args):
        sys.stderr.write(f'[{self.address_string()}] '
                          f'{format % args}\n')

    def _serve(self, status, headers, body):
        self.send_response(status)
        response_headers = dict(headers)
        existing = {key.lower() for key in response_headers}
        for key, value in SECURITY_HEADERS.items():
            if key.lower() not in existing:
                response_headers[key] = value
        for k, v in response_headers.items():
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _dispatch(self, method):
        expected_port = int(self.server.server_address[1])
        if not _valid_host_header(self.headers.get('Host'), expected_port):
            self._serve(*_json(403, {'error': 'invalid_host'}))
            return

        url = urllib.parse.urlparse(self.path)
        path = url.path
        qs = urllib.parse.parse_qs(url.query)

        if ((path == '/api/query' or method == 'POST')
                and not _same_origin_request(self)):
            self._serve(*_json(403, {'error': 'cross_site_request_rejected'}))
            return

                    
        for pattern, mm, fn in API_ROUTES:
            if mm != method:
                continue
            m = pattern.match(path)
            if not m:
                continue
            try:
                result = fn(self, m.groupdict(), qs)
            except Exception:
                _log_current_exception(f'unhandled request error: {method} {path}')
                result = _json(500, {'error': 'internal_server_error'})
            if result is None:
                                                                   
                return
            self._serve(*result)
            return

                              
        if method != 'GET':
            self._serve(*_json(405, {'error': 'method_not_allowed'}))
            return

                                   
        if path.startswith('/static/'):
            rel = path[len('/static/'):].lstrip('/')
            full = _safe_join(STATIC_DIR, rel)
            if full is None:
                self._serve(*_text(403, 'forbidden'))
                return
            self._serve(*_file(full))
            return

               
        if path == '/' or path == '/index.html':
            self._serve(*_file(os.path.join(STATIC_DIR, 'index.html')))
            return

                                                               
        if path.startswith('/download/'):
                                      
            parts = path[len('/download/'):].split('/', 1)
            if len(parts) == 2:
                u, fn = parts
                if not _valid_username(u) or os.path.basename(fn) != fn:
                    self._serve(*_text(400, 'invalid path'))
                    return
                full = _safe_join(_CFG['artifacts_root'], u,
                                  OUTPUT_SUBDIR, fn)
                if full is None:
                    self._serve(*_text(403, 'forbidden'))
                    return
                self._serve(*_file(full))
                return

        self._serve(*_text(404, 'not found'))

    def do_GET(self):
        self._dispatch('GET')

    def do_POST(self):
        self._dispatch('POST')


                                                                             
      
                                                                             

def main():
    p = argparse.ArgumentParser(description='Instagram OSINT local web app')
    p.add_argument('--port', type=int, default=8000)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--artifacts', default=DEFAULT_ARTIFACT_ROOT,
                    help='artifact root dir')
    args = p.parse_args()

    if not _is_loopback_hostname(args.host):
        p.error('--host must be localhost or an explicit loopback IP address')

    if not os.path.isdir(args.artifacts):
        print(f'[!] artifact dir yok: {args.artifacts}', file=sys.stderr)
        sys.exit(1)

    _CFG['artifacts_root'] = os.path.abspath(args.artifacts)

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f'http://{args.host}:{args.port}/'
    print(f'[*] Instagram OSINT web app')
    print(f'[*] artifacts: {_CFG["artifacts_root"]}')
    print(f'[*] listening  {url}')
    print(f'[*] users      {url}api/users')
    print(f'[*] CTRL+C to stop')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n[*] shutting down')
    finally:
                                                                    
                                                                   
        srv.server_close()


if __name__ == '__main__':
    main()
