"""Tek komutluk Instagram OSINT uygulama baslaticisi."""

import argparse
import importlib.util
import ipaddress
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from importlib import metadata
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REQUIREMENTS = APP_DIR / 'requirements.txt'
DEFAULT_ARTIFACTS_DIR = APP_DIR / 'data' / 'artifacts'
DEFAULT_ENV_FILE = APP_DIR / '.env'

PIP_TO_IMPORT = {
    'requests': 'requests',
    'curl-cffi': 'curl_cffi',
    'beautifulsoup4': 'bs4',
    'Pillow': 'PIL',
    'paho-mqtt': 'paho.mqtt.client',
    'networkx': 'networkx',
    'playwright': 'playwright',
}

MINIMUM_VERSIONS = {
    'requests': '2.31',
    'curl-cffi': '0.15.0',
    'beautifulsoup4': '4.12',
    'Pillow': '10.0',
    'paho-mqtt': '1.6',
    'networkx': '3.1',
    'playwright': '1.42',
}


def _find_env(explicit: str | None = None) -> Path | None:
    candidate = Path(explicit).expanduser() if explicit else DEFAULT_ENV_FILE
    return candidate.resolve() if candidate.is_file() else None


def _env_has_required_values(path: Path) -> bool:
    values = {}
    for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key.strip()] = value
    session_id = values.get('IG_SESSIONID', '')
    viewer_id = values.get('IG_DS_USER_ID', '')
    return bool(session_id and viewer_id.isdigit() and len(viewer_id) <= 30)


def _is_loopback_host(host: str) -> bool:
    if str(host).strip().lower() == 'localhost':
        return True
    try:
        return ipaddress.ip_address(str(host).strip()).is_loopback
    except ValueError:
        return False


def _numeric_version(value: str) -> tuple[int, ...]:
    """Compare the stable numeric versions used by requirements.txt."""
    parts = []
    for segment in value.split('+', 1)[0].split('.'):
        match = re.match(r'(\d+)', segment)
        if not match:
            break
        parts.append(int(match.group(1)))
    return tuple(parts or [0])


def _version_is_supported(installed: str, minimum: str) -> bool:
    installed_parts = _numeric_version(installed)
    minimum_parts = _numeric_version(minimum)
    width = max(len(installed_parts), len(minimum_parts))
    installed_parts += (0,) * (width - len(installed_parts))
    minimum_parts += (0,) * (width - len(minimum_parts))
    if installed_parts != minimum_parts:
        return installed_parts > minimum_parts
                                                                             
    return not re.search(r'(?:dev|a|b|rc)\d*', installed, re.IGNORECASE)


def _dependency_issues() -> list[str]:
    issues = []
    for package, module in PIP_TO_IMPORT.items():
        try:
            available = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            available = False
        if not available:
            issues.append(f'{package} (missing)')
            continue
        minimum = MINIMUM_VERSIONS[package]
        try:
            installed = metadata.version(package)
        except metadata.PackageNotFoundError:
            issues.append(f'{package} (version metadata missing)')
            continue
        if not _version_is_supported(installed, minimum):
            issues.append(f'{package} {installed} (requires >= {minimum})')
    return issues


def _install_missing_dependencies(skip: bool) -> None:
    issues = _dependency_issues()
    if not issues:
        print('[+] Dependencies are installed at supported versions')
        return
    print('[!] Missing or outdated packages: ' + ', '.join(issues))
    if skip:
        raise SystemExit(
            '[X] --skip-deps was used, but dependencies are missing or outdated. '
            'Upgrade from requirements.txt first.')
    rc = subprocess.call(
        [sys.executable, '-m', 'pip', 'install', '--upgrade',
         '-r', str(REQUIREMENTS)])
    if rc:
        raise SystemExit('[X] Dependency installation failed')
    remaining = _dependency_issues()
    if remaining:
        raise SystemExit(
            '[X] Dependencies still do not satisfy requirements: '
            + ', '.join(remaining))


def main() -> None:
    parser = argparse.ArgumentParser(description='Instagram OSINT web app')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--skip-deps', action='store_true')
    parser.add_argument(
        '--env-file',
        help='path to the local Instagram cookie file (default: ./.env)')
    parser.add_argument(
        '--artifacts',
        help='artifact directory (prefer a non-synced encrypted location)')
    args = parser.parse_args()

    if sys.version_info < (3, 10):
        raise SystemExit('[X] Python 3.10 veya ustu gerekli')

    if not _is_loopback_host(args.host):
        raise SystemExit(
            '[X] This unauthenticated application is localhost-only. '
            'Use 127.0.0.1, localhost, or ::1.')
    if not 1 <= args.port <= 65535:
        raise SystemExit('[X] Port must be between 1 and 65535')

    _install_missing_dependencies(args.skip_deps)
    env_file = _find_env(args.env_file)
    if not env_file:
        sample = APP_DIR / '.env.example'
        raise SystemExit(
            f'[X] Cookie file not found. Copy {sample} to '
            f'{args.env_file or DEFAULT_ENV_FILE}.')
    if not _env_has_required_values(env_file):
        raise SystemExit(
            '[X] IG_SESSIONID and a numeric IG_DS_USER_ID are required')

    if os.name != 'nt' and env_file.stat().st_mode & 0o077:
        print('[!] Cookie file is readable by other users. Run: '
              f'chmod 600 "{env_file}"')

    artifacts_dir = Path(
        args.artifacts
        or os.environ.get('IG_ARTIFACT_ROOT', '')
        or DEFAULT_ARTIFACTS_DIR).expanduser().resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    child_env = os.environ.copy()
    child_env['IG_ENV_FILE'] = str(env_file)
    child_env['IG_ARTIFACT_ROOT'] = str(artifacts_dir)
    child_env['PYTHONIOENCODING'] = 'utf-8'

    url_host = f'[{args.host}]' if ':' in args.host else args.host
    url = f'http://{url_host}:{args.port}/'
    print('[+] Ayarlar hazir')
    print(f'[+] Data directory: {artifacts_dir}')
    print(f'[+] Arayuz: {url}')

    if not args.no_browser:
        def open_ui():
            time.sleep(1.2)
            webbrowser.open(url)
        threading.Thread(target=open_ui, daemon=True).start()

    cmd = [sys.executable, '-m', 'backend', '--host', args.host,
           '--port', str(args.port), '--artifacts', str(artifacts_dir)]
    try:
        raise SystemExit(subprocess.call(cmd, cwd=APP_DIR, env=child_env))
    except KeyboardInterrupt:
        print('\n[*] Kapatildi')


if __name__ == '__main__':
    main()
