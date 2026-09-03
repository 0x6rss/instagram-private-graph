"""Artifact loader — disk JSON'larini guvenli sekilde okur, missing dosya
ve corrupt JSON durumunda log + bos dict doner."""

import json
import os
import re
import tempfile
from typing import Any

from .config import ARTIFACT_FILES, DEFAULT_ARTIFACT_ROOT


_USERNAME_RE = re.compile(r'[A-Za-z0-9._]{1,30}\Z', re.ASCII)


class TargetScopeConflict(RuntimeError):
    """Raised when artifacts in one username directory name different targets."""


class Artifacts:
    """Tek bir target_username icin tum artifact dosyalarini lazy yukler."""

    def __init__(self, username: str, root: str = DEFAULT_ARTIFACT_ROOT):
        if (not isinstance(username, str)
                or not _USERNAME_RE.fullmatch(username)
                or username in ('.', '..')):
            raise ValueError('invalid_artifact_username')
        self.username = username
        self.root = os.path.realpath(os.path.abspath(os.fspath(root)))
        self.target_dir = self._safe_child(
            self.root, username, 'username')
        self._cache: dict[str, Any] = {}
        self.load_log: list[dict] = []                             
        self.target_pk: str | None = None
        self.target_scope_sources: dict[str, list[str]] = {}
        self._target_scope_checked = False

    @staticmethod
    def _validate_component(value: str, label: str) -> str:
        if (not isinstance(value, str) or not value or value in ('.', '..')
                or '\x00' in value or '/' in value or '\\' in value
                or os.path.basename(value) != value):
            raise ValueError(f'invalid_artifact_{label}')
        return value

    @classmethod
    def _safe_child(cls, base: str, component: str, label: str) -> str:
        component = cls._validate_component(component, label)
        base_real = os.path.realpath(base)
        candidate = os.path.realpath(os.path.join(base_real, component))
        try:
            if os.path.commonpath((base_real, candidate)) != base_real:
                raise ValueError(f'invalid_artifact_{label}')
        except ValueError:
            raise ValueError(f'invalid_artifact_{label}') from None
        return candidate

                         
    def _read(self, filename: str):
        path = self._safe_child(self.target_dir, filename, 'filename')
        if not os.path.exists(path):
            self.load_log.append({'file': filename, 'status': 'missing'})
            return None
        try:
            with open(path, encoding='utf-8') as f:
                d = json.load(f)
            self.load_log.append({'file': filename, 'status': 'ok',
                                   'size': os.path.getsize(path)})
            return d
        except (OSError, json.JSONDecodeError) as e:
            self.load_log.append({'file': filename, 'status': 'error',
                                   'error': type(e).__name__, 'msg': str(e)[:120]})
            return None

    def get(self, key: str):
        """key ARTIFACT_FILES'taki sembolik isim."""
        if key in self._cache:
            return self._cache[key]
        fname = ARTIFACT_FILES.get(key)
        if not fname:
            return None
        d = self._read(fname)
        self._cache[key] = d
        return d

                                 
    def resolve_target_pk(self) -> str | None:
        """Resolve explicit target IDs by consensus and fail closed on conflict.

        Only documented top-level target fields are considered. The one known
        exceptions are ``critical_intel.identity.pk`` and the legacy
        ``critical_intel.intel.pk``. Arbitrary nested ``pk`` values are
        candidate/user IDs and must never establish target scope.
        """
        if self._target_scope_checked:
            return self.target_pk

                                                                            
                                                                           
        source_specs = (
            ('critical_intel', (('pk',), ('target_pk',),
                                ('identity', 'pk'), ('intel', 'pk'))),
            ('presence_intel', (('pk',), ('target_pk',))),
            ('target_internal', (('target_pk',), ('pk',))),
            ('cluster_union', (('pk',), ('target_pk',))),
            ('discover_p32', (('pk',), ('target_pk',))),
            ('chaining_cluster', (('pk',), ('target_pk',))),
            ('archeology_p29', (('target_pk',), ('pk',))),
            ('tagged_feed', (('target_pk',), ('pk',))),
            ('tag_search_cluster', (('target_pk',), ('pk',))),
            ('news_inbox', (('target_pk',), ('pk',))),
            ('phase34_followgraph', (('target_pk',), ('pk',))),
            ('reciprocal_phase35', (('target_pk',), ('pk',))),
            ('banyan_phase37', (('target_pk',), ('pk',))),
        )
        ids_to_sources: dict[str, list[str]] = {}
        for key, field_paths in source_specs:
            d = self.get(key)
            if not isinstance(d, dict):
                continue
            for field_path in field_paths:
                pk = d
                for field in field_path:
                    pk = pk.get(field) if isinstance(pk, dict) else None
                if pk is None or str(pk).strip() == '':
                    continue
                pk_s = str(pk).strip()
                source = f'{key}.{".".join(field_path)}'
                if not pk_s.isdigit():
                    raise TargetScopeConflict(
                        f'target_scope_invalid: {source} has non-numeric target id')
                sources = ids_to_sources.setdefault(pk_s, [])
                if source not in sources:
                    sources.append(source)

        self.target_scope_sources = ids_to_sources
        if len(ids_to_sources) > 1:
            summary = '; '.join(
                f'{pk}={",".join(sources)}'
                for pk, sources in sorted(ids_to_sources.items()))
            raise TargetScopeConflict(
                f'target_scope_conflict: {self.username}: {summary}')

        self.target_pk = next(iter(ids_to_sources), None)
        self._target_scope_checked = True
        return self.target_pk

                         
    def list_present(self) -> list[str]:
        """Disk'te var olan artifact key'lerini dondur."""
        present = []
        for key, fname in ARTIFACT_FILES.items():
            if os.path.exists(os.path.join(self.target_dir, fname)):
                present.append(key)
        return present

    def list_missing(self) -> list[str]:
        return [k for k in ARTIFACT_FILES
                if not os.path.exists(os.path.join(self.target_dir,
                                                     ARTIFACT_FILES[k]))]

    def output_dir(self, subdir: str) -> str:
        path = self._safe_child(self.target_dir, subdir, 'output_subdir')
        os.makedirs(path, exist_ok=True)
        return path

    def write_json(self, subdir: str, name: str, obj) -> str:
        path = self._safe_child(
            self.output_dir(subdir), name, 'output_filename')
        self._atomic_text_write(
            path, json.dumps(obj, indent=2, ensure_ascii=False, default=str))
        return path

    def write_text(self, subdir: str, name: str, text: str) -> str:
        path = self._safe_child(
            self.output_dir(subdir), name, 'output_filename')
        self._atomic_text_write(path, text)
        return path

    @staticmethod
    def _atomic_text_write(path: str, text: str) -> None:
        fd, temp_path = tempfile.mkstemp(
            prefix=f'.{os.path.basename(path)}.', suffix='.tmp',
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

    def open_csv(self, subdir: str, name: str):
        """csv.writer icin path acilir — Windows '\\r\\r\\n' onleyici (newline='').
        Caller close etmek zorunda."""
        path = self._safe_child(
            self.output_dir(subdir), name, 'output_filename')
        f = open(path, 'w', encoding='utf-8', newline='')
        return f, path
