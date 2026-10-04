# Live evaluation with Gemini

The Gemini adapter uses Python's standard-library HTTPS client. No Google SDK or
additional runtime dependency is required. It sends questions and evidence to
Google's `generateContent` endpoint and applies the existing evaluation pipeline.

## Get a key and select a model

Create a key in [Google AI Studio](https://aistudio.google.com/apikey). Choose a
text-generation model eligible for your project's free tier using
[Google's current pricing](https://ai.google.dev/gemini-api/docs/pricing).
Availability and quotas vary; the program does not verify billing settings or
free-tier eligibility. Use the API model ID, not its display name. Both
`gemini-...` and `models/gemini-...` formats are accepted.

## Enter the key in zsh

The key prompt hides your input and keeps the key itself out of shell history.
It stays in the terminal environment and is not written to source or reports.
Do not paste the key into chat.

```zsh
cd /Users/shivam/Downloads/rag-eval
source .venv/bin/activate
read -s "GEMINI_API_KEY?Gemini API key: "
export GEMINI_API_KEY
echo
read "RAG_EVAL_MODEL?Free-tier model ID: "
```

## Check three cases first

```sh
python -m rag_eval \
  --generator gemini \
  --model "$RAG_EVAL_MODEL" \
  --retriever bm25 \
  --limit 3 \
  --request-interval 15 \
  --out results/gemini-smoke
```

This plans six generation requests; temporary server failures can add retries.
The first three cases are known-answer questions, so they check integration
rather than representing the full dataset.
It writes `report_bm25_gemini.md` and `report_bm25_gemini.json` under the specified
directory. The console prints the request count before starting and the metric
summary after completion.

## Run the complete evaluation

```sh
python -m rag_eval \
  --generator gemini \
  --model "$RAG_EVAL_MODEL" \
  --retriever bm25 \
  --request-interval 15 \
  --out results/gemini-full
```

All 37 cases make 74 generation requests: retrieved-context and oracle-context
generation per question. At 15-second spacing, allow at least about 18 minutes.
Use `--retriever bm25,tfidf` to compare both retrievers (148 requests).

Spacing does not guarantee the run fits your quota. Check requests-per-minute,
token, and daily quotas in AI Studio. See
[Google's rate-limit guide](https://ai.google.dev/gemini-api/docs/rate-limits).

## Errors and limitations

- Missing key: set `GEMINI_API_KEY` in the same terminal that runs evaluation.
- HTTP 400: check the key, model, and generation settings.
- HTTP 403: check project permissions and API availability.
- HTTP 404: check the model ID and its `generateContent` support.
- HTTP 429: increase spacing for per-minute limits; exhausted daily quotas require
  waiting for reset. Quota errors are not retried automatically.
  When Google includes structured details, the error identifies daily versus
  per-minute quotas, numeric limits, and retry delay. A reported limit of zero
  means there is currently no capacity under that model/project quota. Daily
  request quotas reset at midnight Pacific; longer spacing does not restore them.
  Quotas are per project, so another key in the same project does not reset usage.
  Check AI Studio's active limits before starting a 74-request run.
- HTTP 500/502/503/504: temporary server errors are retried up to three times,
  with 5-, 10-, and 20-second backoff, extended when your request interval or a
  numeric `Retry-After` header requires it. Retry waits are logged without exposing
  credentials. A provider-requested wait above 60 seconds stops the run for a
  later retry. Use `--max-retries 0` to disable retries or select a value up to 5
  (backoff capped at 60 seconds). Persistent service failures require waiting or
  choosing another available free-tier model.
- Empty, blocked, or truncated response: evaluation stops without treating the
  provider failure as model abstention or scoring it as an answer.

On failure, the current retriever's report is not written. Completed answers are
saved atomically in `OUT/.checkpoints/`; rerun the same command to resume. Earlier
reports remain in place. Use `--no-resume` for a fresh trial. Per-case progress
shows which answers were cached and which were generated.

The adapter uses temperature zero and a 2,048-token output budget. Thought parts
are excluded from answer parsing. The exact `INSUFFICIENT_EVIDENCE` marker counts
as abstention. Reports record model, output budget, interval, retry limit, case limit, and
dataset fingerprints without the API key.

Mocked tests cover the integration; no live results are claimed until a real run
completes. API contract: [Google generateContent reference](https://ai.google.dev/api/generate-content).
