# LLM Reliability & Evaluation Framework

A reusable workflow for evaluating RAG systems that **separates retrieval, generation and source
attribution into independently testable stages**, so a bad answer can be traced to its root cause
instead of being scored as one opaque number.

Pure Python 3.10+, no runtime dependencies (`anthropic` and `pytest` optional).

**Use Groq for free-tier hosted evaluation.** See [GROQ_SETUP.md](GROQ_SETUP.md)
for key setup, a six-request smoke check, and the complete run. No extra SDK is
needed. [Gemini setup](GEMINI_SETUP.md) is also available.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the complete data flow, file-by-file
responsibilities, data contracts, extension points, and scoring limitations.

Install in an isolated environment with `python3 -m venv .venv`, activate it with
`source .venv/bin/activate`, then run `pip install '.[test]'`. Installation includes
the sample datasets and provides the `rag-eval` command. Outputs default to
`results/` under the current working directory.

```
python -m rag_eval                       # run BM25 + TF-IDF baselines, write results/
python -m rag_eval --retriever bm25 --k 5 --min-coverage 0.5
python scripts/sweep_threshold.py        # abstention trade-off curve
python -m pytest -q tests                # framework and regression tests

pip install anthropic && export ANTHROPIC_API_KEY=...
python -m rag_eval --generator anthropic --model YOUR_AVAILABLE_MODEL_ID

# After setting GROQ_API_KEY in your terminal:
python -m rag_eval --generator groq --model openai/gpt-oss-20b --retriever bm25 --limit 3 --request-interval 15 --out results/groq-smoke
```

## Design

| Stage | Question it answers | Isolation trick | Metrics |
|---|---|---|---|
| 1. Retrieval | Did the right chunk surface? | Generator is never called | Recall@1/3/5, MRR, 95% bootstrap CIs |
| 2. Generation | Given good evidence, is the answer right / does it abstain? | **Oracle context** = gold chunks + the case's hard negatives (negatives placed first) | Answer-OK rate, abstention accuracy |
| 3. Attribution | Are citations real, supporting and from the right source? | Scored on both end-to-end and oracle answers | Citation faithfulness, validity, precision vs gold, forbidden-source rate |
| 4. Diagnosis | Why did this case fail? | Compares stages 1-3 per case | 8-way root-cause taxonomy |

**Test-case types** (`data/cases.jsonl`, 37 cases over a fictional 18-passage corpus, so no pretraining leakage):

- **Known-answer (22)**: includes 4 deliberately paraphrased queries (vocabulary gap).
- **Unanswerable (7)**: correct behaviour is abstention.
- **Adversarial (8)**: prompt injection in the corpus and in the query, a stale superseded policy, a near-duplicate distractor product, a false-premise question, negation, and a lexically-similar question with no answer.

**Citation faithfulness**: an answer sentence is supported when >=80% of its content words appear in the
*cited* chunks (not merely anywhere in the context). Citations must also exist in the provided context,
point at a gold chunk when one exists, and never cite a forbidden (stale / injected / distractor) chunk.

**Root-cause taxonomy**: `RETRIEVAL_MISS`, `DISTRACTOR_INTERFERENCE` (gold present and the generator
passes on oracle context, suggesting retrieved noise misled it), `WRONG_ANSWER_GIVEN_GOLD` (fails even with oracle context),
`OVER_ABSTENTION`, `UNSUPPORTED_GENERATION`, `ADVERSARIAL_COMPLIANCE`, `CITATION_UNFAITHFUL`, `PASS`.

Oracle context includes annotated hard negatives, so distractor interference is
a diagnostic heuristic from the oracle comparison, not a separate clean-context
experiment. Saved JSON includes actual citations, oracle context IDs, run settings,
and (for CLI runs) input SHA-256 hashes. Undefined metrics serialize as `null`.

## Baseline results (BM25, extractive generator, k=3)

| Stage | Result |
|---|---|
| Retrieval (28 cases with gold) | Recall@1 **0.821** [0.68, 0.93], Recall@3 **0.929** [0.82, 1.00], Recall@5 **0.964**, MRR **0.878** [0.77, 0.96] |
| Generation, oracle context | Answer-OK **0.622** (known 0.68, unanswerable 0.86, adversarial 0.25) |
| Attribution (answered cases) | Faithfulness 1.00, citation precision 1.00, citation-OK 0.909, forbidden source cited 9.1% |
| End to end | Pass rate **0.649** [0.49, 0.78] |

End-to-end failures (13 of 37): 7 over-abstentions, 2 retrieval misses, 2 unsupported generations,
1 injection compliance, 1 wrong answer given gold.

**What the error analysis shows**

- Retrieval is *not* the main bottleneck (Recall@3 = 0.93). Most failures sit in generation, which a single end-to-end score would hide.
- The 2 retrieval misses are pure vocabulary gaps ("scrambled" vs "encrypted", "certifications" vs "certified"); this is the case for dense or hybrid retrieval.
- The baseline follows an injected instruction (`a08`) and answers a lexically similar but unanswerable question (`a06`, `u01`). Faithfulness is 1.00 anyway: **the answer is faithful to a source that should not have been trusted**. Faithfulness alone is not a safety metric, which is why forbidden-source and forbidden-phrase checks exist.
- Abstention threshold sweep (`scripts/sweep_threshold.py`): raising `min_coverage` from 0.4 to 0.8 drives hallucinations on unanswerable cases from 3 to 0, but over-abstention rises from 3 to 14 cases. Default (0.6) was fixed in advance, not tuned on this set.

## Extending

- **Retriever**: any object with `.name` and `.search(query, k) -> [(doc_id, score)]` (dense, hybrid, reranker).
- **Generator**: any object with `.generate(question, context_docs) -> Answer`. Anthropic, Gemini, and Groq adapters are included.
- **Support judge**: implement `SupportJudge.supported(claim, evidence)` to replace the lexical check with NLI or an LLM judge.
- **Data**: add JSONL lines to `data/`; the schema is `Case` / `Doc` in `rag_eval/types.py`.

## Limitations (read before quoting numbers)

- The corpus and cases are small and synthetic, so confidence intervals are wide (e.g. pass rate 0.49-0.78). Absolute numbers illustrate the method; they are not a benchmark.
- BM25 and TF-IDF tie on every metric here; an 18-passage corpus cannot separate them.
- The baseline generator is deterministic and extractive, chosen as a reproducible lower bound. Hosted adapters are tested with mocks; the build environment has no live API keys. Gemini's three-case smoke run was completed separately by the user, but no full live evaluation has been verified here.
- The lexical support judge can be fooled by paraphrase, and it cannot detect contradictions (it would accept "Starter has an uptime guarantee" if the words overlap). Use an NLI/LLM judge for production decisions.
- Answer correctness is substring matching against accepted aliases, which is strict for free-form LLM output.
