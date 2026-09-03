"""Bidirectional confirmation.

Bir pk hem Phase 29 (target -> X likes/comments) hem Phase 30 (X -> target
tag) icinde varsa: iki yonlu kanitlanmis sosyal halka uyesi. Phase 32
real_connection veya phase31 news_event ile guclendiren ek kanit alir.
"""

from .config import WEIGHTS
from .person import PersonRegistry


def confirm_bidirectional(registry: PersonRegistry):
    counters = {'bidirectional_p29_p30': 0,
                 'triple_p29_p30_p32': 0,
                 'p29_p31': 0,
                 'bidirectional_p38_p30': 0,
                 'quad_p29_p30_p32_p38': 0}
    for p in registry:
                                                                
        has_p29 = bool(p.likes_to_x or p.comments_to_x)
        has_p38 = bool(p.story_mentioned_by_target_count
                        or p.story_collab_with_target)
        target_to_x = has_p29 or has_p38

                          
        has_p30 = bool(p.tags_of_target_count or p.co_tag_count
                        or p.mentioned_target or p.tag_search_hits)
        has_p32_real = (p.context_class == 'real_connection')
        has_p31 = bool(p.news_events)

        if has_p29 and has_p30:
            counters['bidirectional_p29_p30'] += 1
            p.add_evidence('bidirectional_p29_p30',
                            WEIGHTS['bidirectional_bonus'],
                            {'p29_likes': len(p.likes_to_x),
                             'p29_comments': len(p.comments_to_x),
                             'p30_tags': p.tags_of_target_count,
                             'p30_co_tags': p.co_tag_count})
            if has_p32_real:
                counters['triple_p29_p30_p32'] += 1
                p.add_evidence('triple_confirmation',
                                WEIGHTS['bidirectional_bonus'] // 2,
                                {'note': 'p29 + p30 + p32_real_connection'})
        if has_p29 and has_p31:
            counters['p29_p31'] += 1
            p.add_evidence('cross_p29_p31',
                            WEIGHTS['bidirectional_bonus'] // 4,
                            {'note': 'archeology + news_inbox'})

                                                                    
                                                                        
        if has_p38 and has_p30 and not has_p29:
            counters['bidirectional_p38_p30'] += 1
            p.add_evidence('bidirectional_p38_p30',
                            WEIGHTS['bidirectional_bonus'],
                            {'p38_story_mentions':
                                p.story_mentioned_by_target_count,
                             'p38_collab': p.story_collab_with_target,
                             'p30_tags': p.tags_of_target_count})

                                                                      
        if has_p29 and has_p30 and has_p32_real and has_p38:
            counters['quad_p29_p30_p32_p38'] += 1
            p.add_evidence('quad_confirmation',
                            WEIGHTS['bidirectional_bonus'],
                            {'note': ('p29 + p30 + p32_real + p38_story —'
                                       ' 4 bagimsiz kaynakta gorundu')})
    return counters
