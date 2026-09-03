"""Aggregate explicitly target-scoped mutual-follower metadata.

Instagram returns ``mutual_followers_count`` relative to the authenticated
viewer. ``chaining.ingest_chaining_cluster`` leaves Person's field unset unless
the artifact proves ``viewer_pk == target_pk``. This module therefore consumes
only prevalidated target-relative values. The legacy weight is supporting model
evidence, not a calibrated probability or follower-edge proof.
"""

from .config import WEIGHTS
from .person import PersonRegistry


def apply_mutual_bonus(registry: PersonRegistry):
    counters = {'with_mfc': 0, 'max_mfc': 0, 'sum_bonus': 0.0}
    factor = WEIGHTS['mutual_followers_count_factor']
    cap = WEIGHTS['mutual_followers_max_bonus']
    for p in registry:
        mfc = p.mutual_followers_count
        if (not isinstance(mfc, int) or isinstance(mfc, bool) or mfc <= 0):
            continue
        bonus = min(mfc * factor, cap)
        p.add_evidence('mutual_followers_bonus', bonus,
                        {'mfc': mfc, 'factor': factor, 'cap': cap,
                         'scope': 'target_to_candidate',
                         'note': ('Prevalidated target-relative metadata; not '
                                  'proof of a direct follow edge.')})
        counters['with_mfc'] += 1
        counters['max_mfc'] = max(counters['max_mfc'], mfc)
        counters['sum_bonus'] += bonus
    return counters
