"""Web sorgusu icin hizli username -> PK on hazirligi."""

import json
import os
import re
import sys
import tempfile
import time

from poc import ARTIFACT_ROOT, discover_pk, load_env_cookies


USERNAME_RE = re.compile(r'^[A-Za-z0-9._]{1,30}$')


def main() -> int:
    username = (sys.argv[1] if len(sys.argv) > 1 else '').strip()
    if not USERNAME_RE.fullmatch(username):
        print('[!] gecersiz username')
        return 2

    cookies = load_env_cookies()
    if not cookies:
        print('[!] .env icinde IG_SESSIONID ve IG_DS_USER_ID gerekli')
        return 2

    print(f'[*] target pk hazirlaniyor: @{username}')
    pk, _ = discover_pk(username, cookies)
    if not pk:
        print('[!] pk bulunamadi; cookie/IP rate-limit veya username kontrol et')
        return 1

    target_dir = os.path.join(ARTIFACT_ROOT, username)
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, 'critical_intel.json')
    payload = {
        'pk': str(pk),
        'username': username,
        'prepared_at': time.time(),
        'prepared_by': 'web_search_exact_match',
    }
    fd, temp_path = tempfile.mkstemp(
        prefix='.critical_intel.', suffix='.tmp', dir=target_dir)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    print(f'[+] target hazir: pk={pk}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
