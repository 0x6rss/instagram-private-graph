"""Console / Markdown rapor."""

import io


def _fmt_pct(n, total):
    if not total:
        return '0%'
    return f'{n * 100 / total:.0f}%'


def render_text_report(meta: dict, registry, by_tier_map,
                        cotag_edges, alt_account_data,
                        loc_data, friendship_summary, target_internal):
    """Insan-okur rapor. registry sirali olmaya gerek yok; by_tier_map zaten
    grouplanmis."""
    buf = io.StringIO()
    w = buf.write

    w('=' * 78 + '\n')
    w(f'RELATIONSHIP ENGINE — target: {meta.get("username")} '
      f'(pk={meta.get("target_pk")})\n')
    w('=' * 78 + '\n\n')

                               
    w('SOURCE COVERAGE\n')
    w('-' * 78 + '\n')
    src = meta.get('sources') or {}
    for k, v in src.items():
        w(f'  {k:<20}  {v}\n')
    w('\n')

                              
    w('TIER BREAKDOWN\n')
    w('-' * 78 + '\n')
    total = sum(len(v) for v in by_tier_map.values())
    for tier in ('intimate', 'known', 'acquaintance', 'algorithmic', 'noise'):
        cnt = len(by_tier_map.get(tier, []))
        w(f'  {tier:<14} {cnt:>4} ({_fmt_pct(cnt, total)})\n')
    w(f'  {"TOTAL":<14} {total:>4}\n\n')

                                                   
    for tier in ('intimate', 'known', 'acquaintance'):
        people = by_tier_map.get(tier, [])
        if not people:
            continue
        w(f'TOP {tier.upper()} ({len(people)} kisi)\n')
        w('-' * 78 + '\n')
        w(f'  {"score":>6}  {"pk":<14}  {"username":<28} {"flags":<10} '
          f'evidence_summary\n')
        for p in people[:30]:
            flags = []
            if p.is_private:
                flags.append('P')
            if p.is_verified:
                flags.append('V')
            if p.same_avatar_uploader:
                flags.append('ALT')
            if p.context_class == 'real_connection':
                flags.append('R')
            elif p.context_class == 'suggested':
                flags.append('S')
                                                      
            hc = p.hop_class
            if hc == '1hop_stable':
                flags.append('★')
            elif hc == '1hop_strong':
                flags.append('1S')
            elif hc == '1hop_confirmed':
                flags.append('1H')
            elif hc == '2hop_suspect':
                flags.append('2H')
            f = ''.join(flags)
            ev = []
            if len(p.likes_to_x) or len(p.comments_to_x):
                ev.append(f'p29[L{len(p.likes_to_x)}/C{len(p.comments_to_x)}]')
            if p.tags_of_target_count:
                ev.append(f'tags={p.tags_of_target_count}')
            if p.co_tag_count:
                ev.append(f'cotag={p.co_tag_count}')
            if p.cluster_module_count:
                ev.append(f'p28[{p.cluster_module_count}m]')
            if p.tag_search_hits:
                ev.append(f'ts={p.tag_search_hits}')
            if p.news_events:
                ev.append(f'news={len(p.news_events)}')
            if p.mutual_followers_count:
                ev.append(f'mfc={p.mutual_followers_count}')
            if p.shared_locations:
                ev.append(f'loc={len(p.shared_locations)}')
            if p.cotag_2hop_neighbors:
                ev.append(f'2hop={len(p.cotag_2hop_neighbors)}')
            ev_str = ' '.join(ev) or '-'
            un = (p.username or '?')[:26]
            w(f'  {p.score:>6.1f}  {p.pk:<14}  @{un:<27} {f:<10} {ev_str}\n')
        w('\n')

                                           
    bidir = meta.get('bidirectional') or {}
    if bidir:
        w('BIDIRECTIONAL CONFIRMATIONS\n')
        w('-' * 78 + '\n')
        for k, v in bidir.items():
            w(f'  {k:<32} = {v}\n')
        w('\n')

                           
    if cotag_edges:
        w(f'CO-TAG 2-HOP GRAPH ({len(cotag_edges)} qualified edges)\n')
        w('-' * 78 + '\n')
        for e in cotag_edges[:20]:
            a_name = (registry.by_pk(e['a']).username
                       if registry.by_pk(e['a']) else e['a'])
            b_name = (registry.by_pk(e['b']).username
                       if registry.by_pk(e['b']) else e['b'])
            w(f'  @{a_name:<26}  --[{e["overlap"]}]--  @{b_name}\n')
        w('\n')

                                      
    same_target = alt_account_data.get('same_uploader_as_target') or []
    cross = alt_account_data.get('cross_upload_groups') or {}
    close_pairs = alt_account_data.get('close_avatar_pairs') or []
    if same_target or cross or close_pairs:
        w('ALT-ACCOUNT CANDIDATES (avatar forensics)\n')
        w('-' * 78 + '\n')
        if same_target:
            w(f'  same_avatar_uploader_as_target: {len(same_target)} pk\n')
            for pk in same_target[:10]:
                p = registry.by_pk(pk)
                un = p.username if p else '?'
                w(f'    @{un} (pk={pk}) — target uploaded this avatar\n')
        if cross:
            w(f'  cross_uploader_groups: {len(cross)} grouped uploaders\n')
            for upl, pks in list(cross.items())[:10]:
                w(f'    uploader={upl} -> {len(pks)} accounts: '
                  f'{", ".join(pks[:8])}\n')
        if close_pairs:
            w(f'  close_avatar_timestamp_pairs: {len(close_pairs)}\n')
            for pair in close_pairs[:5]:
                a = registry.by_pk(pair["a"])
                b = registry.by_pk(pair["b"])
                w(f'    @{a.username if a else pair["a"]} <-> '
                  f'@{b.username if b else pair["b"]} '
                  f'({pair["delta_s"]}s arayla)\n')
        w('\n')

                         
    if loc_data and loc_data.get('shared_locations'):
        w(f'SHARED LOCATIONS\n')
        w('-' * 78 + '\n')
        w(f'  distinct_locations  = {loc_data.get("distinct_locations")}\n')
        w(f'  shared_locations    = {loc_data.get("shared_locations")}\n')
        w(f'  persons_attributed  = {loc_data.get("persons_attributed")}\n\n')

                                    
    if friendship_summary:
        w('FRIENDSHIP SAMPLE AGGREGATE (cluster sample)\n')
        w('-' * 78 + '\n')
        for k, v in friendship_summary.items():
            w(f'  {k:<24} = {v}\n')
        w('\n')

                                          
    fs_t = (target_internal or {}).get('friendships_show')
    if fs_t and isinstance(fs_t, dict):
        w('TARGET <-> VIEWER (Phase 33 friendships/show)\n')
        w('-' * 78 + '\n')
        for k, v in sorted(fs_t.items()):
            if k == 'status':
                continue
            w(f'  {k:<35} = {v}\n')
        w('\n')

    return buf.getvalue()
