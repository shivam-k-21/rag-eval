# Scoring version 3.0 and fresh comparison

## What changed

`--judge structured` adds bounded semantic rules to the conservative lexical
judge: unambiguous company references across sentences in a cited document,
explicit membership in a data-center list, a rate-limit status paraphrase,
and upper/lower quantity-bound preservation. A safe extended refusal is
excluded from factual support and forbidden-phrase checks only when the
entire sentence matches. Appended prompt disclosures remain scored.

This is a rule-based judge, not general semantic entailment. Unsupported
paraphrases can still be rejected and lexical matches can still be misleading.
`--judge conservative` remains the default with version 2.0 behavior for
reproducibility. `--judge structured` records version 3.0. The optional Groq
judge now has explicit reference, membership and quantity-scope instructions,
and uses version 3.0 refusal handling; it has not been validated live here.

## Fixed grader probes

Validation-v1 was written before implementing the new judge. It uses different
names, locations and quantities, with 28 support probes and eight refusal
probes. The expected labels and rule design were authored by the same assistant,
so the experiment is not an independent semantic benchmark. No validation
labels were changed or grader rules tuned in response to probe results.

| Judge | Support decisions | False acceptances | False rejections | Refusal decisions |
|---|---:|---:|---:|---:|
| Conservative v2 | 21/28 (75.0%) | 5 | 2 | 6/8 (75.0%) |
| Structured v3 | 28/28 (100.0%) | 0 | 0 | 8/8 (100.0%) |

All verdicts, labels, and input hashes are saved in
`results/judge-validation/validation.json`. Finite probe success does not
establish general semantic accuracy.

## Saved holdout replay

The original Groq answers were regraded separately using `--judge structured`:
11/12 pass, matching the assistant audit. h03 still fails because it turns a
deadline into an exact duration. The original v2 report remains 8/12. Neither
the answer text nor retrieval changed, and this is not a new model run.
This previously audited set informed the new rules, so the replay is a
regression check rather than new holdout evidence.

## Controlled fresh RAG comparison

Validation-v1 has a separate 12-document Nimbus corpus and 24 questions. Both
retrievers used the same deterministic extractive generator, K=3,
StructuredSupportJudge, threshold 0.6 and identical input hashes. No retrieval
aliases or generation thresholds were tuned on these outcomes.

| Metric | BM25 | Expanded BM25 |
|---|---:|---:|
| Recall@1, 20 gold cases | 70.0% | 80.0% |
| Recall@3, 20 gold cases | 95.0% | 100.0% |
| MRR | 0.825 | 0.900 |
| End-to-end passes | 13/24 (54.2%) | 13/24 (54.2%) |
| Retrieval misses | 1 | 0 |
| Over-abstentions | 9 | 10 |
| Unsupported generations | 1 | 1 |

The retrieval improvement did not improve extractive end-to-end accuracy.
The generator still uses its original vocabulary and coverage heuristic,
which often abstains even with gold evidence. Original report artifacts and
a fingerprinted comparison manifest are under
`results/validation-comparison-extractive/`. This small synthetic comparison
does not establish performance on external documents.

## Completed matched live Groq comparison

The user subsequently completed the validation-v1 comparison using Groq
`qwen/qwen3.8-27b`, K=3, StructuredSupportJudge v3.0 and the same 24 cases.
Both report hashes, dataset fingerprints and matched settings were verified
against `results/validation-comparison-groq/comparison.json`.

| Metric | BM25 | Expanded BM25 |
|---|---:|---:|
| Recall@1, 20 gold cases | 70.0% | 80.0% |
| Recall@3, 20 gold cases | 95.0% | 100.0% |
| MRR | 0.825 | 0.900 |
| Automated end-to-end passes | 21/24 (87.5%) | 21/24 (87.5%) |
| Retrieval misses | 1 | 0 |

Expanded retrieval removed the encryption retrieval miss, but its generated
answer was flagged for citation support, so the automated pass rate did not
increase. Both runs correctly abstained on all four unanswerable cases.

Remaining flags are v06 (deletion deadline), v08 (trial duration), and v14
(encryption; a retrieval miss for BM25 and support flag for expanded BM25).
They require source-level review before interpreting them as model errors:
v06 says the deadline is 45 days, but the accepted alias requires “within
45 days”; v08 paraphrases the 21-day trial; v14 uses “information” for “data.”
The structured judge and substring correctness check remain bounded. No
rules or labels were changed using these new results, and no reviewed score
is claimed for this set. Its automated reports remain unchanged.

## Reproduce the matched live comparison

The completed API run was made in the user's keyed terminal. To reproduce or
resume it, run in the terminal where `GROQ_API_KEY` is exported:

```sh
cd /Users/shivam/Downloads/rag-eval
source .venv/bin/activate
python scripts/run_comparison.py \
  --generator groq \
  --model qwen/qwen3.8-27b \
  --request-interval 15 \
  --out results/validation-comparison-groq
```

This plans up to 96 generation requests (two stages, 24 cases, two retrievers).
Identical contexts can share checkpointed answers, reducing actual calls.
Rerun the same command to resume. Use another output directory and `--no-resume`
for a separate fresh repetition. No hosted support-judge calls are needed for
the structured judge. Inspect the paired reports and manifest in the visualizer
after Refresh. Keep model, K, judge and data fixed when comparing retrieval.

For reproducibility:

```sh
python scripts/validate_judge.py
python scripts/run_comparison.py
python scripts/rescore_report.py \
  results/groq-holdout/report_expanded_bm25_groq.json \
  --cases data/holdout_cases.jsonl --judge structured \
  --out results/groq-holdout-structured
python visualizer/server.py
```

## Next external validation

Keep validation-v1 frozen. Have an independent reviewer label a new set of
realistic questions, answers and supporting passages, especially relation
swaps, ambiguous references and numeric bounds. Cross-check semantic-judge
decisions against that annotation. The current artifact work is local; no
repository or website was published to an external service.
