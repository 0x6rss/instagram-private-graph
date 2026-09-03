"""Cikti format'lari — JSON + CSV + GEXF (NetworkX yuklu ise)."""

import csv
import datetime as _dt
import os

from .loader import Artifacts
from .person import PersonRegistry
from .tiers import by_tier


_FORMULA_PREFIXES = ('=', '+', '-', '@')


def _csv_safe_cell(value):
    """Neutralize spreadsheet formulas while preserving CSV data.

    ``csv.writer`` handles quoting but does not prevent a spreadsheet from
    executing cells that begin with formula metacharacters. Prefix risky text
    with an apostrophe; numeric Python values remain numeric.
    """
    if not isinstance(value, str) or not value:
        return value
    significant = value.lstrip(' \t\r\n')
    if (significant.startswith(_FORMULA_PREFIXES)
            or value[0] in ('\t', '\r', '\n')):
        return "'" + value
    return value


class _SafeCsvWriter:
    def __init__(self, file_obj):
        self._writer = csv.writer(file_obj)

    def writerow(self, row):
        self._writer.writerow([_csv_safe_cell(cell) for cell in row])


def _score_sort_key(person):
    try:
        score = float(person.score)
    except (TypeError, ValueError):
        score = 0.0
    return person.hop_class != 'unknown', score


def _person_export_dict(person):
    """Add explicit score validity without breaking the numeric legacy field."""
    payload = person.to_dict()
    payload['score_valid'] = bool(
        getattr(person, 'score_valid', person.hop_class != 'unknown'))
    payload['score_semantics'] = 'uncalibrated_model_confidence'
    return payload


def export_relationships_json(arts: Artifacts, registry: PersonRegistry,
                                meta: dict, subdir: str,
                                target_intel: dict | None = None,
                                activity: dict | None = None):
    """relationships_ranked.json — pk basina tum ozet + evidence + score.

    target_intel: target hakkinda konsolide metadata (kategorize edilmis)
    activity:     target'in cluster icine yaptigi etkilesim timeline'i (Phase 29)
    """
    persons = sorted(registry, key=_score_sort_key, reverse=True)
    payload = {
        'username': arts.username,
        'target_pk': arts.target_pk,
        'meta': meta,
        'target_intel': target_intel or {},
        'activity': activity or {},
        'tiers': {tier: [p.pk for p in pls]
                   for tier, pls in by_tier(registry).items()},
        'people': [_person_export_dict(p) for p in persons],
    }
    return arts.write_json(subdir, 'relationships_ranked.json', payload)


def _iso(ts):
    if not ts:
        return ''
    try:
        return _dt.datetime.fromtimestamp(
            ts, tz=_dt.timezone.utc).isoformat()
    except (OSError, ValueError, OverflowError):
        return ''


def export_csv(arts: Artifacts, registry: PersonRegistry, subdir: str):
    """Tabular CSV — pk, username, score, tier, key signal counts."""
    persons = sorted(registry, key=_score_sort_key, reverse=True)
    f, path = arts.open_csv(subdir, 'relationships_ranked.csv')
    try:
        w = _SafeCsvWriter(f)
        w.writerow([
            'pk', 'username', 'full_name', 'score', 'score_valid',
            'tier', 'tier_rank',
            'hop_class', 'phase32_rank',
            'is_private', 'is_verified', 'context_class',
            'cluster_modules_n', 'mfc',
            'p29_likes', 'p29_comments',
            'p30_tagger_count', 'p30_co_tag_count', 'p30_mentioned',
            'tag_search_hits', 'news_events',
            'shared_locations', 'cotag_2hop_neighbors',
            'same_avatar_uploader', 'avatar_ts_close',
            'fs_following', 'fs_followed_by', 'fs_blocking', 'fs_restricted',
            'last_seen_iso',
        ])
        for p in persons:
            fs = p.friendship_status or {}
            w.writerow([
                p.pk, p.username or '', p.full_name or '',
                p.score, int(bool(getattr(
                    p, 'score_valid', p.hop_class != 'unknown'))),
                p.tier or '', p.tier_rank or '',
                p.hop_class or '',
                p.phase32_rank if p.phase32_rank is not None else '',
                p.is_private if p.is_private is not None else '',
                p.is_verified if p.is_verified is not None else '',
                p.context_class or '',
                p.cluster_module_count or 0,
                p.mutual_followers_count
                if p.mutual_followers_count is not None else '',
                len(p.likes_to_x), len(p.comments_to_x),
                p.tags_of_target_count, p.co_tag_count,
                int(bool(p.mentioned_target)),
                p.tag_search_hits, len(p.news_events),
                len(p.shared_locations), len(p.cotag_2hop_neighbors),
                int(bool(p.same_avatar_uploader)),
                int(bool(p.avatar_ts_close)),
                int(bool(fs.get('following'))),
                int(bool(fs.get('followed_by'))),
                int(bool(fs.get('blocking'))),
                int(bool(fs.get('is_restricted'))),
                _iso(p.last_seen_ts),
            ])
    finally:
        f.close()
    return path


def export_edges_csv(arts: Artifacts, registry: PersonRegistry,
                      target_pk: str | None, cotag_edges: list[dict],
                      subdir: str):
    """Edge list — Gephi/NetworkX/Cytoscape import edilebilir."""
    f, path = arts.open_csv(subdir, 'edges.csv')
    try:
        w = _SafeCsvWriter(f)
        w.writerow(['source', 'target', 'weight', 'type'])
        target = str(target_pk) if target_pk else 'TARGET'
        for p in registry:
            if p.score <= 0:
                continue
            w.writerow([target, p.pk, round(p.score, 2),
                         f'target_to_{p.tier or "unknown"}'])
        for edge in cotag_edges or []:
            w.writerow([edge['a'], edge['b'], edge.get('overlap', 1),
                         'cotag_2hop'])
    finally:
        f.close()
    return path


def export_nodes_csv(arts: Artifacts, registry: PersonRegistry,
                      target_pk: str | None, subdir: str):
    f, path = arts.open_csv(subdir, 'nodes.csv')
    try:
        w = _SafeCsvWriter(f)
        w.writerow(['id', 'label', 'tier', 'score', 'score_valid',
                     'is_private', 'is_verified', 'context_class'])
        if target_pk:
            w.writerow([str(target_pk), arts.username or 'TARGET',
                         'target', '', '', '', '', ''])
        for p in registry:
            w.writerow([
                p.pk,
                p.username or p.full_name or p.pk,
                p.tier or '',
                round(p.score, 2),
                int(bool(getattr(
                    p, 'score_valid', p.hop_class != 'unknown'))),
                int(bool(p.is_private)) if p.is_private is not None else '',
                int(bool(p.is_verified)) if p.is_verified is not None else '',
                p.context_class or '',
            ])
    finally:
        f.close()
    return path


def export_gexf(arts: Artifacts, registry: PersonRegistry,
                 target_pk: str | None, cotag_edges: list[dict], subdir: str):
    """Optional NetworkX GEXF export. NetworkX yoksa skip + None doner."""
    try:
        import networkx as nx
    except ImportError:
        return None

    g = nx.DiGraph()
    target = str(target_pk) if target_pk else 'TARGET'
    g.add_node(target, label=arts.username or 'TARGET', tier='target',
                score=0, kind='target')

    for p in registry:
        g.add_node(p.pk, label=(p.username or p.full_name or p.pk),
                    tier=p.tier or '',
                    score=p.score,
                    score_valid=int(bool(getattr(
                        p, 'score_valid', p.hop_class != 'unknown'))),
                    is_private=int(bool(p.is_private)),
                    is_verified=int(bool(p.is_verified)),
                    context=p.context_class or '',
                    kind='person')
        if p.score > 0:
            g.add_edge(target, p.pk, weight=p.score, type='target_to_person')

    for edge in cotag_edges or []:
        g.add_edge(edge['a'], edge['b'],
                    weight=edge.get('overlap', 1), type='cotag_2hop')
        g.add_edge(edge['b'], edge['a'],
                    weight=edge.get('overlap', 1), type='cotag_2hop')

    path = os.path.join(arts.output_dir(subdir), 'graph.gexf')
    nx.write_gexf(g, path)
    return path
