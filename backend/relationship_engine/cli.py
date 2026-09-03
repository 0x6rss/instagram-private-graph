"""CLI orchestrator — tum modulleri sirayla cagirir, ciktilari yazar."""

import argparse
import io
import os
import sys
import time

from .config import DEFAULT_ARTIFACT_ROOT, OUTPUT_SUBDIR, TIER_THRESHOLDS
from .loader import Artifacts
from .person import PersonRegistry

from . import (chaining, discover, archeology, tagged, news,
                friendship, mutual, bidirectional, cotagged_graph,
                temporal, altaccount, locations, scoring, tiers,
                exporter, reporter, filters, verification, target_intel,
                reciprocal, banyan as banyan_module, bootstrap, stories)


def _ensure_utf8():
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                       errors='replace', line_buffering=True)


def run(username: str, root: str = DEFAULT_ARTIFACT_ROOT,
         subdir: str = OUTPUT_SUBDIR, drop_algorithmic: bool = False) -> dict:
    arts = Artifacts(username, root)
    if not os.path.isdir(arts.target_dir):
        raise SystemExit(f'[!] artifact dir yok: {arts.target_dir}')
    target_pk = arts.resolve_target_pk()
    print(f'[*] target = {username} (pk={target_pk})')
    print(f'[*] artifact dir = {arts.target_dir}')
    present = arts.list_present()
    missing = arts.list_missing()
    print(f'[*] present: {len(present)} artifacts | missing: {len(missing)}')
    if missing:
        print(f'    missing: {missing}')

    registry = PersonRegistry()
    sources_meta = {}

                          
    print('\n[1/12] Phase 28 cluster_union ingest...')
    sources_meta['cluster_union'] = chaining.ingest_cluster_union(arts, registry)

    print('[2/12] Phase 26 chaining_cluster ingest...')
    sources_meta['chaining_cluster'] = chaining.ingest_chaining_cluster(
        arts, registry)

    print('[2b/12] Phase 28 baseline friendship_grid ingest...')
    sources_meta['friendship_grid'] = friendship.ingest_friendship_grid(
        arts, registry)

    print('[3/12] Phase 32 discover_chaining ingest...')
    sources_meta['discover_p32'] = discover.ingest_discover_p32(arts, registry)

    print('[4/12] Phase 29 archeology ingest...')
    sources_meta['archeology_p29'] = archeology.ingest_archeology(
        arts, registry)

    print('[5/12] Phase 30 tagged_feed ingest...')
    sources_meta['tagged_feed'] = tagged.ingest_tagged_feed(arts, registry)

    print('[6/12] Phase 26 tag_search ingest...')
    sources_meta['tag_search'] = tagged.ingest_tag_search(arts, registry)

    print('[7/12] Phase 31 news_inbox ingest...')
    sources_meta['news_inbox'] = news.ingest_news_inbox(
        arts, registry, target_pk)

    print('[7b/12] Phase 35 reciprocal chaining ingest...')
    sources_meta['reciprocal'] = reciprocal.ingest_reciprocal(arts, registry)

    print('[7c/12] Phase 37 banyan share intimacy ingest...')
    sources_meta['banyan'] = banyan_module.ingest_banyan(arts, registry)

    print('[7d/12] Bootstrap users ingest (scores/bootstrap/users)...')
    sources_meta['bootstrap'] = bootstrap.ingest_bootstrap_users(
        arts, registry, target_pk)

    print('[7e/12] Phase 38 story mentions ingest (target story)...')
    sources_meta['story_mentions'] = stories.ingest_story_mentions(
        arts, registry, target_pk)
    cov = (sources_meta['bootstrap'].get('coverage') or {})
    if cov.get('warning'):
        print(f'    [!] coverage uyarisi: {cov["warning"]}')

                                                                              
                                                     
    if target_pk:
        registry.drop(target_pk)

                             
    print('[8/12] Friendship aggregate...')
    fs_summary = friendship.aggregate_friendship(registry)
    sources_meta['friendship_aggregate'] = fs_summary

    print('[9/12] Mutual followers bonus...')
    sources_meta['mutual_bonus'] = mutual.apply_mutual_bonus(registry)

    print('[10/13] Bidirectional confirmation...')
    bidir = bidirectional.confirm_bidirectional(registry)
    sources_meta['bidirectional'] = bidir

    print('[11/13] Co-tag 2-hop graph...')
    cotag_data = cotagged_graph.build_2hop_graph(arts, registry, target_pk)
    sources_meta['cotag_2hop'] = {k: v for k, v in cotag_data.items()
                                    if k != 'edges'}

    print('[12/13] 1-hop vs 2-hop verification...')
    sweep_n = ((sources_meta.get('cluster_union') or {}).get('sweep_n')
               or 15)
    multi_run = ((sources_meta.get('discover_p32') or {}).get('multi_run_count')
                  or 1)
                                                                        
                                                                 
    total_p32 = 80
    sources_meta['hop_verification'] = verification.classify_hop(
        registry, sweep_n=sweep_n, total_p32=total_p32, multi_run=multi_run)

                                                                      
    print('[13a/14] Target intel consolidation...')
    target_meta = target_intel.build_target_intel(arts)
    activity = target_intel.build_activity_timeline(arts)
    sources_meta['target_intel_built'] = bool(target_meta)
    sources_meta['activity_present'] = activity.get('present', False)

    print('[13/13] Temporal + alt-account + locations...')
    sources_meta['temporal'] = temporal.analyze(registry)
    sources_meta['altaccount'] = altaccount.analyze(registry, target_pk)
    sources_meta['locations'] = locations.analyze(arts, registry, target_pk)

                                                                                         
    real, algo_only = filters.split(registry)
    sources_meta['filters'] = {
        'real_persons': len(real),
        'algorithmic_only_persons': len(algo_only),
    }
    if drop_algorithmic:
        for p in algo_only:
            registry.drop(p.pk)

                          
    sorted_persons = scoring.finalize_scores(registry)
    tier_counts = tiers.classify(registry)
    sources_meta['tier_counts'] = tier_counts

                                           
    target_internal = friendship.load_target_internal(arts)

                       
    out_dir = arts.output_dir(subdir)
    print(f'\n[*] writing outputs -> {out_dir}')

    meta = {
        'username': username,
        'target_pk': target_pk,
        'generated_at': time.time(),
        'sources': sources_meta,
        'load_log': arts.load_log,
        'tier_thresholds': dict(TIER_THRESHOLDS),
        'bidirectional': bidir,
    }

    json_path = exporter.export_relationships_json(
        arts, registry, meta, subdir,
        target_intel=target_meta, activity=activity)
    csv_path = exporter.export_csv(arts, registry, subdir)
    edges_path = exporter.export_edges_csv(
        arts, registry, target_pk, cotag_data.get('edges') or [], subdir)
    nodes_path = exporter.export_nodes_csv(
        arts, registry, target_pk, subdir)
    gexf_path = exporter.export_gexf(
        arts, registry, target_pk, cotag_data.get('edges') or [], subdir)
    print(f'  -> {json_path}')
    print(f'  -> {csv_path}')
    print(f'  -> {edges_path}')
    print(f'  -> {nodes_path}')
    if gexf_path:
        print(f'  -> {gexf_path}')
    else:
        print('  -> graph.gexf SKIPPED (networkx kurulu degil)')

                 
    by_tier_map = tiers.by_tier(registry)
    text = reporter.render_text_report(
        meta, registry, by_tier_map,
        cotag_data.get('edges') or [],
        sources_meta['altaccount'],
        sources_meta['locations'],
        fs_summary, target_internal)
    text_path = arts.write_text(subdir, 'relationship_report.txt', text)
    print(f'  -> {text_path}')

                              
    print('\n' + text)

    return {
        'json': json_path, 'csv': csv_path, 'edges': edges_path,
        'nodes': nodes_path, 'gexf': gexf_path, 'text': text_path,
        'meta': meta, 'tier_counts': tier_counts,
    }


def main(argv=None):
    _ensure_utf8()
    p = argparse.ArgumentParser(
        description='Relationship engine — phase26_29 artifact aggregator')
    p.add_argument('username', help='target username (artifact dir name)')
    p.add_argument('--artifacts', default=DEFAULT_ARTIFACT_ROOT,
                    help='artifact root dir (default: ../artifacts)')
    p.add_argument('--out', default=OUTPUT_SUBDIR,
                    help='output subdir under artifacts/<username>/')
    p.add_argument('--drop-algorithmic', action='store_true',
                    help='Yalnizca algoritmik (Phase 32 suggested) pk\'lari '
                         'rapordan dusur')
    args = p.parse_args(argv)

    run(args.username, args.artifacts, args.out, args.drop_algorithmic)


if __name__ == '__main__':
    main()
