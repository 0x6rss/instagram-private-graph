"""Temporal pattern analysis.

Person.activity_timestamps icinde Phase 29 (likes, comments) + Phase 30 (tags)
+ Phase 31 (news_inbox) timestamp'leri var. Burada:
  - last_seen_ts hesaplanir
  - recent_activity_bonus eklenir (son N gunde etkilesim)
  - per-person aggregate metrics (first/last/span/by_hour/by_dow) intel.json'a
    yansitilir
"""

import datetime
import time

from .config import RECENT_DAYS, WEIGHTS
from .person import PersonRegistry


def _ts_iso(ts: int):
    if not ts:
        return None
    try:
        return datetime.datetime.fromtimestamp(
            ts, tz=datetime.timezone.utc).isoformat()
    except (OSError, ValueError, OverflowError):
        return None


def _hist_by_hour(ts_list: list[int]) -> dict:
    out = {h: 0 for h in range(24)}
    for ts in ts_list:
        try:
            h = datetime.datetime.fromtimestamp(
                ts, tz=datetime.timezone.utc).hour
            out[h] += 1
        except (OSError, ValueError, OverflowError):
            continue
    return out


def _hist_by_dow(ts_list: list[int]) -> dict:
    """0=Mon ... 6=Sun"""
    out = {d: 0 for d in range(7)}
    for ts in ts_list:
        try:
            d = datetime.datetime.fromtimestamp(
                ts, tz=datetime.timezone.utc).weekday()
            out[d] += 1
        except (OSError, ValueError, OverflowError):
            continue
    return out


def analyze(registry: PersonRegistry):
    counters = {'with_timestamps': 0, 'recent_active': 0,
                 'overall_first': None, 'overall_last': None,
                 'global_hour_hist': {h: 0 for h in range(24)},
                 'global_dow_hist': {d: 0 for d in range(7)}}
    now = time.time()
    cutoff = now - (RECENT_DAYS * 86400)

    overall_first = None
    overall_last = None

    for p in registry:
        ts_list = sorted(set(p.activity_timestamps))
        if not ts_list:
            continue
        counters['with_timestamps'] += 1
        first_ts = ts_list[0]
        last_ts = ts_list[-1]
        p.last_seen_ts = last_ts

        if overall_first is None or first_ts < overall_first:
            overall_first = first_ts
        if overall_last is None or last_ts > overall_last:
            overall_last = last_ts

                                                                         
                                                              
        ph = _hist_by_hour(ts_list)
        pd = _hist_by_dow(ts_list)
        for h, n in ph.items():
            counters['global_hour_hist'][h] += n
        for d, n in pd.items():
            counters['global_dow_hist'][d] += n

                               
        if last_ts >= cutoff:
            p.add_evidence('recent_activity',
                            WEIGHTS['recent_activity_bonus'],
                            {'last_seen_iso': _ts_iso(last_ts),
                             'days_ago': round((now - last_ts) / 86400, 1)})
            counters['recent_active'] += 1

    counters['overall_first_iso'] = _ts_iso(overall_first) if overall_first else None
    counters['overall_last_iso'] = _ts_iso(overall_last) if overall_last else None
    return counters
