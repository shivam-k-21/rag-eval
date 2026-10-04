# Dataset roles

`cases.jsonl` is the original 37-case development benchmark. Its annotations
were reviewed after observing the Qwen run, including two explicit negative
answer variants for case `a07`. Do not describe those updated annotations or
the vocabulary expansion as independently validated on these same cases.

`holdout_cases.jsonl` contains 12 post-audit checks: 6 known, 3 unanswerable, and
3 adversarial. They were written after the scoring and expansion rules were
implemented, and those rules are not tuned against their results. This is still
a small synthetic check sharing the same 18-passage corpus, not an external
production benchmark. Future changes should use development cases for tuning
and preserve these cases for evaluation, or establish a new held-out set.

Saved reports fingerprint the exact data used. Original Groq reports retain the
original annotation fingerprint. Regraded reports are separate artifacts with
their own reviewed-case fingerprint and a source-report fingerprint.
