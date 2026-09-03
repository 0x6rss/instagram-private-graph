"""Phase 31 news_inbox — viewer-side asimetrik etkilesim feed.

Her event 'profile_id' (actor) ve 'target_id' (object). Target target_pk
ise news_inbox.target_events bunu zaten filtrelemis durumda. Burada role'a
gore actor (target -> X icin actor=target -> X event'in 'target_id'si X olur)
veya target (X -> target -> X actor) ayrimi yaparak X pk'sini cikariyoruz.

Notu: Bu phase asagidaki target_pk'nin VIEWER ile etkilesimi (viewer is X):
phase31 target_events'leri zaten *target == target_pk* var oldugu icin gosterir.
Yani bu yalnizca viewer<->target asimetrik kanit veriyor; viewer'in pk'si X
oluyor (target pk degil).

Bu yuzden burada karsi taraf VIEWER'in pk'si — ki o cluster'da yok. Yine de
target'in news_inbox event'lerini Person registry'de **target** kayitlari icin
not olarak tutmak gereksiz; bu sadece target hakkinda meta-bilgidir.

Burada strateji: target_events icindeki *baska* pk'lar (mention edilen, follow
edilen ucuncu kisi vs. — args.target_id != target_pk olan kisiler) varsa o
pk'lara skor yaz.
"""

from .config import WEIGHTS
from .loader import Artifacts
from .person import PersonRegistry


def ingest_news_inbox(arts: Artifacts, registry: PersonRegistry,
                       target_pk: str | None):
    ni = arts.get('news_inbox') or {}
    events = ni.get('target_events') or []
    if not events:
        return {'loaded': False, 'events': 0}

    target_pk_s = str(target_pk) if target_pk else ''
    counters = {'events': len(events), 'attributed': 0, 'noise': 0}

    for ev in events:
                                                                  
        actor = str(ev.get('profile_id') or '')
        target_field = str(ev.get('target_id') or '')

                                                                       
                                                                       
                                                                     
                                                                        
                                            
        candidates = []
        if actor and actor != target_pk_s:
            candidates.append((actor, 'is_actor_with_target_object'))
        if target_field and target_field != target_pk_s:
            candidates.append((target_field, 'is_object_target_actor'))

        if not candidates:
            counters['noise'] += 1
            continue

        for cand_pk, role in candidates:
            p = registry.get_or_create(cand_pk, ev.get('profile_name')
                                                 if role.startswith('is_actor')
                                                 else None)
            p.news_events.append({
                'story_type': ev.get('story_type'),
                'role_relative_to_target': role,
                'iso': ev.get('iso'),
                'timestamp': ev.get('timestamp'),
                'text': (ev.get('text') or '')[:160],
            })
            ts = ev.get('timestamp')
            if isinstance(ts, (int, float)):
                p.activity_timestamps.append(int(ts))
            p.add_evidence('phase31_news_event',
                            WEIGHTS['p31_event_per'],
                            {'story_type': ev.get('story_type'),
                             'iso': ev.get('iso')})
            counters['attributed'] += 1
    return {'loaded': True, **counters,
            'event_type_counts': ni.get('event_type_counts') or {}}
