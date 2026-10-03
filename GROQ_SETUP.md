# Live evaluation with Groq

Groq is the primary hosted evaluation workflow for this project. The adapter
uses standard-library HTTPS, so no additional Python SDK is required.

Create a **Groq key** in [Groq Console](https://console.groq.com/keys). A Google AI
Studio key cannot authenticate with Groq. The example below uses
`openai/gpt-oss-20b`, currently listed under Groq's free-plan limits. Check your
organization's actual [Limits](https://console.groq.com/settings/limits) before
starting. Availability and quotas can change; billing eligibility is not checked
or changed by this program.

## Set the key privately in zsh

```zsh
cd /Users/shivam/Downloads/rag-eval
source .venv/bin/activate
read -s "GROQ_API_KEY?Groq API key: "
export GROQ_API_KEY
echo
```

This hides your input and keeps the key itself out of command history. Do not
paste it into chat or source files. The adapter sends it in the Authorization
header, and reports never include it.

## Run a smoke check

```sh
python -m rag_eval \
  --generator groq \
  --model openai/gpt-oss-20b \
  --retriever bm25 \
  --limit 3 \
  --request-interval 15 \
  --out results/groq-smoke
```

This plans six generation requests. It produces `report_bm25_groq.md` and
`report_bm25_groq.json`. The three known-answer questions are an integration
check; use the whole dataset for meaningful slices and adversarial evaluation.

## Run all 37 cases

```sh
python -m rag_eval \
  --generator groq \
  --model openai/gpt-oss-20b \
  --retriever bm25 \
  --request-interval 15 \
  --out results/groq-full
```

This plans 74 requests plus retries, taking at least about 18 minutes with this
spacing. `--retriever bm25,tfidf` doubles the planned requests to 148.

## Rate limits and errors

Free-tier use is quota limited. Limits are at organization level and include
requests and tokens per minute/day. Spacing addresses short-term throughput;
exhausted daily capacity requires waiting. Check the actual limits for the model
and organization in your Console. [Groq rate-limit documentation](https://console.groq.com/docs/rate-limits)

- HTTP 401: check `GROQ_API_KEY`; use a Groq key rather than the Gemini key.
- HTTP 400/404: check the available model ID and its supported settings.
- HTTP 403: check organization/model permissions.
- HTTP 429: the adapter retries only when a numeric `Retry-After` of 0-60 seconds
  is supplied. Longer or missing waits stop with quota guidance.
- HTTP 500/502/503/504: up to three retries with exponential backoff by default.
  Backoff and request spacing are both respected. Numeric provider-requested
  waits above 60 seconds stop for a later run. Use `--max-retries 0` to disable
  retries or choose a limit from 0-5.
- Empty, blocked, malformed, or truncated answers stop the run without being
  treated as abstention. Network failures are not retried automatically.

No model switching happens during retries. On failure, partial answers are not
saved and the current retriever's report is not written. Existing reports remain
in place; there is no resume/caching layer.

Groq requests use `max_completion_tokens=2048`, temperature zero, and independent
source-only prompts. GPT-OSS models additionally use low reasoning effort and
exclude reasoning from responses. Scoring reads only `message.content`, not the
separate reasoning field. An exact `INSUFFICIENT_EVIDENCE` answer is abstention.
Model, token budget, reasoning effort, pacing, retry limit, and input hashes are
recorded in reports.

The integration is verified with mocked HTTP tests, not a live Groq key.
API references: [chat completions](https://console.groq.com/docs/api-reference),
[models](https://console.groq.com/docs/models), and
[GPT-OSS reasoning settings](https://console.groq.com/docs/reasoning).
