# Relationship Engine

This package reads previously collected per-target artifacts, normalizes
candidates by Instagram numeric PK, computes an algorithmic association score,
assigns display tiers, and writes JSON, CSV, GEXF, and text outputs. It does not
perform network requests.

Read the project-level [README](../../README.md) before using these outputs. In
particular, model scores are not verified facts or calibrated real-world
probabilities, and graph edges are not confirmed follow relationships.

## Run from the application root

```bash
python -m backend.relationship_engine USERNAME
python -m backend.relationship_engine USERNAME --artifacts /private/artifacts
python -m backend.relationship_engine USERNAME --drop-algorithmic
```

`--drop-algorithmic` removes a limited class of suggestion-only candidates that
lack configured corroboration. It cannot remove every false positive.

## Processing outline

1. Load target-scoped artifacts.
2. Normalize candidate records by numeric PK.
3. Merge profile metadata and evidence traces.
4. Calculate a repeated-appearance estimate from valid current-run samples.
5. Apply only explicitly supported target-scoped model rules.
6. Preserve missing score-producing evidence as `unknown`.
7. Assign compatibility tiers and export reports.

Viewer-bound friendship, inbox, autocomplete, bootstrap, and share-sheet data
describe the authenticated test account. They must not be relabeled as the
target's followers or social circle. Unscoped global captures are not valid
target evidence. Reciprocal recommendation overlap is also not proof of mutual
following or follow direction.

## Score semantics

The main Phase 32 estimate compares two hand-set binomial likelihoods using the
number of successful runs in which a candidate appears. A duplicate PK inside
one response counts once, failed requests are not negative observations, and
historical unions are not current-run repeatability evidence. Phase 28 provides
a separate fallback when a valid current-run module snapshot exists.

The internal raw tier names are retained for compatibility:

| Tier | Range | Meaning |
|---|---:|---|
| `verified` | 99 to 100 | Very high model confidence |
| `high_probability` | 80 to less than 99 | High model confidence |
| `medium_probability` | 40 to less than 80 | Medium model confidence |
| `low_probability` | 15 to less than 40 | Low model confidence |
| `noise` | 0 to less than 15 | Weak or insufficient signal |
| `unknown` | Not scored | No valid score-producing observation |

`verified` is not an Instagram blue-check status and does not mean an
investigator verified the relationship. The model constants and thresholds are
not calibrated against a published ground-truth benchmark. Evidence weights
remain useful trace metadata but are not simply summed into the displayed
score.

Compatibility exports serialize `unknown` with `score = 0` and
`score_valid = false`. The zero is a placeholder and must not be interpreted as
a valid low-confidence observation.

## Outputs

The default output directory is
`data/artifacts/<username>/relationships/` and contains:

- `relationships_ranked.json`
- `relationships_ranked.csv`
- `nodes.csv`
- `edges.csv`
- `graph.gexf` when NetworkX is available
- `relationship_report.txt`

CSV text that begins like a spreadsheet formula is neutralized during export.
JSON and GEXF retain source text and must still be treated as untrusted,
sensitive case data.

## Development constraints

- Validate artifact target PK, viewer scope, run identity, and freshness before
  introducing a source into scoring.
- Keep viewer context separate from target-person evidence.
- Do not infer follower direction from recommendation APIs.
- Add de-identified ground-truth tests and calibration metrics before calling a
  score a probability.
- Use atomic writes for primary JSON and text outputs.
- Preserve raw provenance and explain when a field is context-only.
