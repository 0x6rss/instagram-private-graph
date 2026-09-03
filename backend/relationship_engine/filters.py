"""Algoritmik suggested filtresi — context_class baz aliyor.

Cluster_union'daki Phase 32 'suggested' user'larini ayri bucket'a alir; gercek
sosyal halkadan elendigi icin score'a penalty olarak girer (config.WEIGHTS
'p32_only_suggested').
"""

from .person import PersonRegistry, Person


def is_only_algorithmic(p: Person) -> bool:
    """Eger pk yalnizca Phase 32 'Suggested' kontextinde gorulduyse VE baska
    hicbir interaction (like/comment/tag/co-tag/news) yoksa algoritmik kabul
    et. Stable inner circle uyeleri bu filtreden gecmez."""
    if p.context_class != 'suggested':
        return False
    has_real_signal = (
        p.cluster_module_count is not None and p.cluster_module_count >= 5
        or p.likes_to_x or p.comments_to_x
        or p.tags_of_target_count > 0
        or p.co_tag_count > 0
        or p.news_events
        or p.tag_search_hits > 0
        or p.mentioned_target
    )
    return not has_real_signal


def split(registry: PersonRegistry) -> tuple[list[Person], list[Person]]:
    """(real, algorithmic_only) ayrimi."""
    real = []
    algorithmic = []
    for p in registry:
        if is_only_algorithmic(p):
            algorithmic.append(p)
        else:
            real.append(p)
    return real, algorithmic
