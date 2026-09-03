"""2-hop co-tag graph.

tagged_feed.cluster_pivot.tags_found ve tag_search_cluster.tagged_posts_found
icindeki her postta target ile beraber tag'lenenler 'A' kumesi (= Person'lar
co_tag_count > 0).

2-hop: A icindeki kisilerin baska postlarda **birbirleri ile** co-tag yaptigi
postlar varsa, bu kisiler arasinda bir social tie var. Bunu hesaplamak icin
her tag posttaki co_tagged_users listesini cikariyor, kombinatoriyel olarak
edge'leri sayiyoruz. Edge frekansi >= COTAG_2HOP_MIN_OVERLAP olanlar 2-hop
neighbor olarak isaretlenir.

Algoritma:
  1) Her post p icin co_tag_set(p) = {target} ∪ {co_tagged users in p}
  2) Tum postlardan {(pk_i, pk_j)} pair frekansi sayilir (target dahil edilmez)
  3) 2-hop pair freq >= MIN_OVERLAP olanlar, her iki tarafa cotag_2hop_neighbor
     evidence + score olarak yazilir
"""

from itertools import combinations

from .config import COTAG_2HOP_MIN_OVERLAP, WEIGHTS
from .loader import Artifacts
from .person import PersonRegistry


def _collect_post_groups(arts: Artifacts, target_pk: str) -> list[set]:
    """Her tag-post icin co-tag set'i (target + co_tagged user pks)."""
    groups: list[set] = []

    tf = arts.get('tagged_feed') or {}

    direct_items = (tf.get('direct') or {}).get('items') or []
    for item in direct_items:
        s = {str(target_pk)}
        if item.get('tagger_pk'):
            s.add(str(item['tagger_pk']))
        for co in (item.get('co_tagged_users') or []):
            if co.get('pk'):
                s.add(str(co['pk']))
        if len(s) >= 2:
            groups.append(s)

    pivot_tags = (tf.get('cluster_pivot') or {}).get('tags_found') or []
    for tag in pivot_tags:
        s = {str(target_pk)}
        if tag.get('tagger_pk'):
            s.add(str(tag['tagger_pk']))
        for co in (tag.get('co_tagged_users') or []):
            if co.get('pk'):
                s.add(str(co['pk']))
        if len(s) >= 2:
            groups.append(s)

    ts_data = arts.get('tag_search_cluster') or {}
    for post in (ts_data.get('tagged_posts_found') or []):
        s = {str(target_pk)}
        if post.get('poster_pk'):
            s.add(str(post['poster_pk']))
        for ut in (post.get('usertags_in_post') or []):
            if ut.get('pk'):
                s.add(str(ut['pk']))
        if len(s) >= 2:
            groups.append(s)

    return groups


def build_2hop_graph(arts: Artifacts, registry: PersonRegistry,
                       target_pk: str):
    if not target_pk:
        return {'loaded': False, 'reason': 'no_target_pk'}

    groups = _collect_post_groups(arts, target_pk)
    if not groups:
        return {'loaded': False, 'groups': 0}

    edge_freq: dict[tuple[str, str], int] = {}
    target_pk_s = str(target_pk)
    for g in groups:
                                                              
        members = sorted(g - {target_pk_s})
        for a, b in combinations(members, 2):
            key = (a, b)
            edge_freq[key] = edge_freq.get(key, 0) + 1

    qualified_edges = []
    for (a, b), n in edge_freq.items():
        if n < COTAG_2HOP_MIN_OVERLAP:
            continue
        qualified_edges.append({'a': a, 'b': b, 'overlap': n})
                                              
        for src, dst in ((a, b), (b, a)):
            p = registry.get_or_create(src)
            if dst not in p.cotag_2hop_neighbors:
                p.cotag_2hop_neighbors.append(dst)
            p.cotag_2hop_overlap = max(p.cotag_2hop_overlap, n)
            p.add_evidence('cotag_2hop_neighbor',
                            WEIGHTS['cotag_2hop_neighbor'] * (n - 1),
                            {'neighbor_pk': dst, 'overlap_posts': n})
    return {'loaded': True,
            'groups': len(groups),
            'distinct_edges': len(edge_freq),
            'qualified_edges': len(qualified_edges),
            'min_overlap': COTAG_2HOP_MIN_OVERLAP,
            'edges': qualified_edges[:200]}
