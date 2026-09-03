"""Alt-account / sahte hesap candidate detection.

profile_pic_id  -> '<media_id>_<uploader_pk>'
Eger:
  - cluster icindeki bir X'in avatar uploader_pk'si target_pk ile esit:
        target target avatari yuklemis (calmis) → strong alt-account signal.
  - cluster icindeki iki Person'in avatar uploader_pk'si esit (farkli pk'lar
    ayni uploader'a sahip): aynı kişinin yönettiği hesaplar olabilir.
  - Avatar upload timestamp'leri AVATAR_TS_WINDOW_SECONDS icinde: birlikte
    olusturulmus alt account'lar (toplu upload).

Hesaplama: profile_pic_id IG snowflake-vari format:
    media_id = int(parts[0])
    avatar_ts_ms = (media_id >> 23) + IG_EPOCH_MS
"""

from .config import AVATAR_TS_WINDOW_SECONDS, WEIGHTS
from .person import PersonRegistry


_IG_EPOCH_MS = 1314220021721


def _decode_ppi(ppi: str | None):
    if not ppi or '_' not in str(ppi):
        return None, None
    try:
        media_part, uploader = str(ppi).split('_', 1)
        media_id = int(media_part)
        ts_ms = (media_id >> 23) + _IG_EPOCH_MS
        return uploader, ts_ms
    except (ValueError, TypeError):
        return None, None


def analyze(registry: PersonRegistry, target_pk: str | None):
    """Avatar bazli alt-account analizi."""
    target_pk_s = str(target_pk) if target_pk else None

                  
    for p in registry:
        if not p.profile_pic_id:
            continue
        upl, ts_ms = _decode_ppi(p.profile_pic_id)
        if upl is None:
            continue
        p.avatar_uploader_pk = upl
        p.avatar_uploaded_ts_ms = ts_ms

                                                              
    same_uploader_target = []
    if target_pk_s:
        for p in registry:
            if p.avatar_uploader_pk and p.avatar_uploader_pk == target_pk_s:
                p.same_avatar_uploader = True
                p.add_evidence('avatar_uploader_matches_target',
                                WEIGHTS['avatar_uploader_match'],
                                {'uploader_pk': target_pk_s,
                                 'note': ('target uploaded this account avatar'
                                          ' — strong alt-account / shared-'
                                          'control signal')})
                same_uploader_target.append(p.pk)

                                                                           
    by_upl: dict[str, list] = {}
    for p in registry:
        if p.avatar_uploader_pk:
            by_upl.setdefault(p.avatar_uploader_pk, []).append(p.pk)
    cross_upload_groups = {u: pks for u, pks in by_upl.items()
                            if len(pks) > 1
                            and (target_pk_s is None or u != target_pk_s)}

                                                                     
    ts_pairs = []
    persons_with_ts = [p for p in registry if p.avatar_uploaded_ts_ms]
    persons_with_ts.sort(key=lambda x: x.avatar_uploaded_ts_ms)
    for i, a in enumerate(persons_with_ts):
        for b in persons_with_ts[i + 1:]:
            delta_s = abs(b.avatar_uploaded_ts_ms - a.avatar_uploaded_ts_ms) / 1000
            if delta_s > AVATAR_TS_WINDOW_SECONDS:
                break                                     
            a.avatar_ts_close = True
            b.avatar_ts_close = True
            a.avatar_ts_delta_seconds = int(delta_s)
            b.avatar_ts_delta_seconds = int(delta_s)
            for p in (a, b):
                p.add_evidence('avatar_close_timestamp',
                                WEIGHTS['avatar_close_timestamp'],
                                {'pair_pk': (b.pk if p is a else a.pk),
                                 'delta_seconds': int(delta_s)})
            ts_pairs.append({'a': a.pk, 'b': b.pk, 'delta_s': int(delta_s)})

    return {'avatars_decoded':
                sum(1 for p in registry if p.avatar_uploader_pk),
            'same_uploader_as_target': same_uploader_target,
            'cross_upload_groups': cross_upload_groups,
            'close_avatar_pairs': ts_pairs,
            'window_seconds': AVATAR_TS_WINDOW_SECONDS}
