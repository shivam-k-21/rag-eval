# RAG Observatory

A separate, dependency-free local web application for inspecting saved RAG
evaluations. It does not run a model or require an API key.

From the project root:

```sh
python visualizer/server.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Use `--port 8766` if needed.
Stop the server with Ctrl+C. Refresh reloads reports from disk. Any new
`results/**/report*.json` output appears automatically after Refresh.

## Features

- Run library grouped by dataset, searchable by model or settings.
- End-to-end and oracle answer stages, confidence intervals, and stage metrics
  with their actual denominators. Oracle context may include hard negatives.
- Outcome breakdown, case search, type/outcome filters, and failures-only view.
- Generated answers, inline citations, context order, and expandable sources.
- Side-by-side comparison with warnings for different/missing input fingerprints,
  models, K, judges, scoring versions, case subsets, or saved-answer replays.
- Assistant audit toggle for the original holdout report, bound to its exact
  SHA-256 fingerprint. Stage metrics remain explicitly automated.
- Separate grader-validation table with probe disagreements.
- Import other evaluation JSON files into browser memory and export filtered
  cases as CSV. Imported reports cannot reconstruct their evidence corpus.

## Architecture

`server.py` uses Python's standard HTTP server bound only to 127.0.0.1. It serves
four known assets and `/api/data`. The bundle reads report JSON, matching audit
records, and judge-validation output. Source text loads only if the corpus is
inside the project and its hash matches the report. Changed or unavailable
corpora are labeled rather than substituted. Checkpoints and reports resolving
outside the project are excluded; no arbitrary file route is exposed.

`index.html` provides semantic controls and accessible labels. `styles.css`
defines a responsive editorial layout with system fonts, restrained semantic
color, visible focus states and reduced-motion support. `app.js` holds local
selection/filter state, calculates displayed outcomes, checks comparison
provenance, and renders report strings with `textContent`. It never executes
HTML from answers or sources. CSV export quotes values and guards spreadsheet
formula prefixes.

The app does not write reports, change grades, access credentials, or make
provider calls. Imported reports disappear on reload. This is a local review
tool; no hosting or account system is included.
